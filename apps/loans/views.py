from datetime import date

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.accounts.permissions import (
    AuditorOrAboveMixin,
    admin_required,
    auditor_or_above,
    cashier_required,
    day_open_required,
    manager_required,
)
from apps.core.account_utils import amount_to_words as _amount_to_words
from apps.core.account_utils import generate_account_number

from .forms import (
    EMICollectionForm,
    GuarantorForm,
    GuarantorFormSet,
    LoanApplicationForm,
    LoanApprovalForm,
    LoanCollateralForm,
    LoanProductForm,
)
from .models import EMISchedule, LoanAccount, LoanCollateral, LoanGuarantor, LoanProduct, LoanRepayment
from .services import (
    approve_loan,
    collect_emi,
    disburse_loan,
    reject_loan,
    validate_loan_application,
)


@auditor_or_above
def loan_list(request):
    loans = LoanAccount.objects.select_related('member', 'loan_product', 'branch')
    if not request.user.can_access_all_branches:
        loans = loans.filter(branch=request.current_branch)

    status_filter = request.GET.get('status', '')
    if status_filter:
        loans = loans.filter(status=status_filter)
    else:
        loans = loans.exclude(status__in=['rejected', 'written_off'])

    loans = loans.order_by('-applied_date')
    paginator = Paginator(loans, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(
        request,
        'loans/list.html',
        {
            'loans': page_obj,
            'status_filter': status_filter,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'paginator': paginator,
        },
    )


@auditor_or_above
def loan_detail(request, pk):
    loan = get_object_or_404(
        LoanAccount.objects.select_related('member', 'loan_product', 'branch', 'director_recommendation'),
        pk=pk,
    )
    if not request.user.can_access_all_branches and loan.branch != request.current_branch:
        messages.error(request, 'You do not have access to this loan.')
        return redirect('loans:list')

    from .models import LoanGuarantor
    from apps.shares.models import ShareHolding

    guarantors = loan.guarantors.select_related('guarantor_member__branch').all()
    for g in guarantors:
        g.active_count = LoanGuarantor.active_guarantee_count(g.guarantor_member)
        holding = ShareHolding.objects.filter(member=g.guarantor_member, status='active').first()
        g.share_count = holding.share_count if holding else 0
        g.share_value = holding.total_amount if holding else 0
    collaterals = loan.collaterals.all()
    emi_schedule = EMISchedule.objects.filter(loan=loan).order_by('installment_no')
    repayments = LoanRepayment.objects.filter(loan=loan).order_by('-payment_date')[:20]

    approval_form = None
    emi_form = None
    if loan.status == 'applied':
        approval_form = LoanApprovalForm(initial={'approved_amount': loan.applied_amount})
    elif loan.status in ('disbursed', 'npa'):
        emi_form = EMICollectionForm(initial={'loan_id': loan.pk})

    product = loan.loan_product
    guarantor_count = guarantors.count()
    guarantor_ok = (
        not product.requires_guarantor
        or guarantor_count >= product.min_guarantors
    )
    collateral_ok = (not loan.loan_product.requires_collateral or
                     loan.collaterals.exists())

    has_interest_slab = False
    if loan.gl_head:
        from apps.accounting.models import InterestMaster
        has_interest_slab = InterestMaster.objects.filter(account_head=loan.gl_head, is_active=True).exists()

    from .models import StandingInstruction
    standing_instructions = StandingInstruction.objects.filter(loan=loan).order_by('-charge_date')

    return render(
        request,
        'loans/detail.html',
        {
            'loan': loan,
            'guarantors': guarantors,
            'collaterals': collaterals,
            'emi_schedule': emi_schedule,
            'repayments': repayments,
            'approval_form': approval_form,
            'emi_form': emi_form,
            'guarantor_ok': guarantor_ok,
            'collateral_ok': collateral_ok,
            'guarantor_count': guarantor_count,
            'min_guarantors': product.min_guarantors if product.requires_guarantor else 0,
            'has_interest_slab': has_interest_slab,
            'standing_instructions': standing_instructions,
        },
    )


@cashier_required
@day_open_required
def loan_apply(request):
    import json as _json

    if request.current_branch is None:
        messages.warning(request, 'Please select a specific branch before applying for a loan.')
        return redirect('loans:list')

    products_qs = LoanProduct.objects.filter(is_active=True)
    products_json = _json.dumps(
        [
            {
                'id': p.pk,
                'name': p.name,
                'interest_rate': str(p.interest_rate),
                'penal_interest_rate': str(p.penal_interest_rate),
                'max_amount': str(p.max_amount),
                'max_tenure_months': p.max_tenure_months,
                'requires_guarantor': p.requires_guarantor,
                'requires_collateral': p.requires_collateral,
                'min_guarantors': p.min_guarantors,
                'max_guarantors': p.max_guarantors,
            }
            for p in products_qs
        ]
    )

    if request.method == 'POST':
        form = LoanApplicationForm(request.POST)
        guarantor_formset = GuarantorFormSet(request.POST, prefix='guarantors')

        if form.is_valid():
            member = form.cleaned_data['member']
            product = form.cleaned_data['loan_product']
            amount = form.cleaned_data['applied_amount']

            errors = validate_loan_application(member, product, amount)
            if errors:
                for e in errors:
                    messages.error(request, e)
            else:
                try:
                    with transaction.atomic():
                        loan = form.save(commit=False)
                        loan.branch = request.current_branch
                        loan.applied_date = date.today()
                        loan.status = 'applied'
                        loan.interest_rate = product.interest_rate
                        loan.penal_interest_rate = product.penal_interest_rate
                        loan.loan_no = generate_account_number(request.current_branch, '010')
                        loan.created_by = request.user
                        loan.save()

                        guarantor_formset = GuarantorFormSet(
                            request.POST,
                            prefix='guarantors',
                            instance=loan,
                        )
                        if guarantor_formset.is_valid():
                            saved = [f for f in guarantor_formset.save() if f.guarantor_member_id]
                            guarantor_count = len(saved)

                            if product.requires_guarantor and guarantor_count < product.min_guarantors:
                                raise ValueError(
                                    f'This loan requires at least {product.min_guarantors} guarantor(s). '
                                    f'Only {guarantor_count} provided.'
                                )
                            if product.max_guarantors and guarantor_count > product.max_guarantors:
                                raise ValueError(
                                    f'Maximum {product.max_guarantors} guarantor(s) allowed. '
                                    f'{guarantor_count} provided.'
                                )
                        else:
                            errors = []
                            for gf in guarantor_formset:
                                for _, errs in gf.errors.items():
                                    errors.extend(errs)
                            if product.requires_guarantor:
                                raise ValueError(
                                    'Guarantor details are invalid. '
                                    + (' '.join(errors) if errors else 'Please fix the errors below.')
                                )
                            if errors:
                                raise ValueError(' '.join(errors))

                    messages.success(request, f'Loan application {loan.loan_no} submitted.')
                    if product.requires_collateral:
                        messages.info(request, 'This loan product requires collateral. Please add collateral now.')
                        return redirect('loans:collateral_add', loan_pk=loan.pk)
                    return redirect('loans:detail', pk=loan.pk)
                except Exception as e:
                    messages.error(request, str(e))
        else:
            for field, errs in form.errors.items():
                for e in errs:
                    messages.error(request, f'{field}: {e}')
    else:
        form = LoanApplicationForm()
        guarantor_formset = GuarantorFormSet(prefix='guarantors')

    if not request.user.can_access_all_branches:
        form.fields['member'].queryset = form.fields['member'].queryset.filter(
            branch=request.current_branch,
        )

    return render(
        request,
        'loans/apply.html',
        {
            'form': form,
            'guarantor_formset': guarantor_formset,
            'products_json': products_json,
        },
    )


@manager_required
def loan_approve(request, pk):
    loan = get_object_or_404(LoanAccount, pk=pk)
    if request.method != 'POST':
        return redirect('loans:detail', pk=pk)

    form = LoanApprovalForm(request.POST)
    if form.is_valid():
        action = form.cleaned_data['action']
        try:
            if action == 'approve':
                approved_amount = form.cleaned_data.get('approved_amount') or loan.applied_amount
                approve_loan(loan, approved_amount, request.user)
                messages.success(request, f'Loan {loan.loan_no} approved for {approved_amount}.')
            else:
                remarks = form.cleaned_data.get('remarks', '')
                reject_loan(loan, remarks, request.user)
                messages.warning(request, f'Loan {loan.loan_no} rejected.')
        except ValueError as e:
            messages.error(request, str(e))
    else:
        for e in form.errors.values():
            messages.error(request, e)

    return redirect('loans:detail', pk=pk)


@manager_required
@day_open_required
def loan_disburse(request, pk):
    loan = get_object_or_404(LoanAccount, pk=pk)
    if request.current_branch is None:
        messages.warning(request, 'Please select a specific branch before disbursing loans.')
        return redirect('loans:detail', pk=pk)
    if request.method != 'POST':
        return redirect('loans:detail', pk=pk)

    try:
        disburse_loan(loan, request.current_branch, request.user)
        messages.success(request, f'Loan {loan.loan_no} disbursed. EMI schedule generated.')
    except ValueError as e:
        messages.error(request, str(e))

    return redirect('loans:detail', pk=pk)


@cashier_required
@day_open_required
def loan_collect(request, pk):
    loan = get_object_or_404(LoanAccount, pk=pk)
    if request.current_branch is None:
        messages.warning(request, 'Please select a specific branch before collecting payments.')
        return redirect('loans:detail', pk=pk)
    if request.method != 'POST':
        return redirect('loans:detail', pk=pk)

    form = EMICollectionForm(request.POST)
    if form.is_valid():
        amount = form.cleaned_data['amount']
        payment_mode = form.cleaned_data['payment_mode']
        try:
            repayment = collect_emi(loan, amount, request.current_branch, request.user, payment_mode)
            messages.success(request, f'Payment of {amount} collected. Receipt: {repayment.receipt_no}')
        except ValueError as e:
            messages.error(request, str(e))
    else:
        for e in form.errors.values():
            messages.error(request, e)

    return redirect('loans:detail', pk=pk)


@auditor_or_above
def loan_product_list(request):
    products = LoanProduct.objects.all().order_by('name')
    return render(request, 'loans/product_list.html', {'products': products})


@admin_required
def loan_product_create(request):
    if request.method == 'POST':
        form = LoanProductForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Loan product created.')
            return redirect('loans:product_list')
    else:
        form = LoanProductForm()
    return render(request, 'loans/product_form.html', {'form': form, 'title': 'Create Loan Product'})


@admin_required
def loan_product_edit(request, pk):
    product = get_object_or_404(LoanProduct, pk=pk)
    if request.method == 'POST':
        form = LoanProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, 'Loan product updated.')
            return redirect('loans:product_list')
    else:
        form = LoanProductForm(instance=product)
    return render(request, 'loans/product_form.html', {'form': form, 'title': f'Edit: {product.name}'})


@auditor_or_above
def loan_charge_list(request):
    from .models import StandingInstruction

    instructions = StandingInstruction.objects.select_related(
        'loan__member',
        'branch',
        'created_by',
    ).order_by('-charge_date')
    if not request.user.can_access_all_branches:
        instructions = instructions.filter(branch=request.current_branch)
    return render(
        request,
        'loans/loan_charge_list.html',
        {
            'instructions': instructions[:100],
        },
    )


@cashier_required
@day_open_required
def loan_charge_create(request):
    from decimal import Decimal, InvalidOperation

    from .models import StandingInstruction
    from .services import add_standing_instruction

    if request.current_branch is None:
        messages.warning(request, 'Please select a specific branch before adding loan charges.')
        return redirect('loans:loan_charge_list')

    loans = LoanAccount.objects.filter(
        status__in=['disbursed', 'npa'],
    ).select_related('member')
    if not request.user.can_access_all_branches:
        loans = loans.filter(branch=request.current_branch)

    if request.method == 'POST':
        loan_id = request.POST.get('loan')
        charge_type = request.POST.get('charge_type', '')
        amount_str = request.POST.get('amount', '0')
        narration = request.POST.get('narration', '')

        try:
            loan = LoanAccount.objects.get(pk=loan_id, status__in=['disbursed', 'npa'])
            amount = Decimal(amount_str)
            if amount <= 0:
                raise ValueError('Amount must be positive.')
            si = add_standing_instruction(
                loan=loan,
                charge_type=charge_type,
                amount=amount,
                branch=request.current_branch,
                narration=narration,
                created_by=request.user,
            )
            messages.success(
                request, f'Loan charge added: {si.get_charge_type_display()} ₹{si.amount:,.2f} on {loan.loan_no}'
            )
            return redirect('loans:loan_charge_list')
        except LoanAccount.DoesNotExist:
            messages.error(request, 'Invalid loan selected.')
        except (InvalidOperation, ValueError) as e:
            messages.error(request, str(e))

    return render(
        request,
        'loans/loan_charge_form.html',
        {
            'loans': loans,
            'charge_types': StandingInstruction.CHARGE_TYPE_CHOICES,
        },
    )


@manager_required
def guarantor_add(request, loan_pk):
    loan = get_object_or_404(LoanAccount, pk=loan_pk)
    branch = getattr(request, 'current_branch', None)
    if branch and not request.user.can_access_all_branches and loan.branch != branch:
        messages.error(request, 'Access denied.')
        return redirect('loans:list')
    if loan.status in ('closed', 'rejected', 'written_off'):
        messages.error(request, 'Cannot add guarantors to this loan.')
        return redirect('loans:detail', pk=loan.pk)

    current_count = loan.guarantors.count()
    product = loan.loan_product
    if product.max_guarantors and current_count >= product.max_guarantors:
        messages.error(request, f'Maximum {product.max_guarantors} guarantors allowed.')
        return redirect('loans:detail', pk=loan.pk)

    if request.method == 'POST':
        form = GuarantorForm(request.POST)
        form._loan = loan
        if form.is_valid():
            guarantor = form.save(commit=False)
            guarantor.loan = loan
            share_account = form.cleaned_data.get('_share_account', '')
            if share_account and not guarantor.guarantor_share_account:
                guarantor.guarantor_share_account = share_account
            guarantor.save()
            messages.success(request, f'Guarantor {guarantor.guarantor_member.name} added.')
            return redirect('loans:detail', pk=loan.pk)
    else:
        form = GuarantorForm()
        form._loan = loan

    return render(request, 'loans/guarantor_form.html', {
        'form': form, 'loan': loan, 'title': 'Add Guarantor',
    })


@manager_required
def guarantor_edit(request, pk):
    guarantor = get_object_or_404(
        LoanGuarantor.objects.select_related('loan', 'loan__loan_product', 'guarantor_member'),
        pk=pk,
    )
    loan = guarantor.loan
    branch = getattr(request, 'current_branch', None)
    if branch and not request.user.can_access_all_branches and loan.branch != branch:
        messages.error(request, 'Access denied.')
        return redirect('loans:list')
    if loan.status in ('closed', 'rejected', 'written_off'):
        messages.error(request, 'Cannot edit guarantors on this loan.')
        return redirect('loans:detail', pk=loan.pk)

    if request.method == 'POST':
        form = GuarantorForm(request.POST, instance=guarantor)
        form._loan = loan
        if form.is_valid():
            g = form.save(commit=False)
            share_account = form.cleaned_data.get('_share_account', '')
            if share_account and not g.guarantor_share_account:
                g.guarantor_share_account = share_account
            g.save()
            messages.success(request, f'Guarantor {g.guarantor_member.name} updated.')
            return redirect('loans:detail', pk=loan.pk)
    else:
        form = GuarantorForm(instance=guarantor)
        form._loan = loan

    return render(request, 'loans/guarantor_form.html', {
        'form': form, 'loan': loan, 'title': f'Edit Guarantor: {guarantor.guarantor_member.name}',
    })


@manager_required
def guarantor_delete(request, pk):
    guarantor = get_object_or_404(
        LoanGuarantor.objects.select_related('loan', 'loan__loan_product', 'guarantor_member'),
        pk=pk,
    )
    loan = guarantor.loan
    branch = getattr(request, 'current_branch', None)
    if branch and not request.user.can_access_all_branches and loan.branch != branch:
        messages.error(request, 'Access denied.')
        return redirect('loans:list')
    if loan.status in ('closed', 'rejected', 'written_off'):
        messages.error(request, 'Cannot modify guarantors on this loan.')
        return redirect('loans:detail', pk=loan.pk)

    if request.method != 'POST':
        return redirect('loans:detail', pk=loan.pk)

    # For disbursed/active loans, enforce minimum guarantor count
    product = loan.loan_product
    if loan.status in ('disbursed', 'npa') and product.requires_guarantor:
        remaining = loan.guarantors.count() - 1
        if remaining < product.min_guarantors:
            messages.error(
                request,
                f'Cannot remove guarantor. Active loans require at least '
                f'{product.min_guarantors} guarantor(s).',
            )
            return redirect('loans:detail', pk=loan.pk)

    name = guarantor.guarantor_member.name
    guarantor.delete()
    messages.success(request, f'Guarantor {name} removed.')
    return redirect('loans:detail', pk=loan.pk)


class EMIReceiptView(AuditorOrAboveMixin, View):
    def get(self, request, repayment_id):
        repayment = get_object_or_404(
            LoanRepayment.objects.select_related(
                'loan__member',
                'loan__loan_product',
                'branch',
                'created_by',
                'emi_schedule',
            ),
            id=repayment_id,
        )
        return render(
            request,
            'receipts/emi_receipt.html',
            {
                'repayment': repayment,
                'amount_words': _amount_to_words(repayment.amount),
            },
        )


@manager_required
def collateral_add(request, loan_pk):
    loan = get_object_or_404(LoanAccount, pk=loan_pk)
    branch = getattr(request, 'current_branch', None)
    if branch and not request.user.can_access_all_branches and loan.branch != branch:
        messages.error(request, 'Access denied.')
        return redirect('loans:list')
    if loan.status in ('closed', 'rejected', 'written_off'):
        messages.error(request, 'Cannot add collateral to this loan.')
        return redirect('loans:detail', pk=loan.pk)

    if request.method == 'POST':
        form = LoanCollateralForm(request.POST, request.FILES)
        if form.is_valid():
            collateral = form.save(commit=False)
            collateral.loan = loan
            collateral.save()
            messages.success(request, f'{collateral.get_collateral_type_display()} collateral added.')
            return redirect('loans:detail', pk=loan.pk)
    else:
        form = LoanCollateralForm()

    return render(request, 'loans/collateral_form.html', {
        'form': form, 'loan': loan, 'title': 'Add Collateral',
    })


@manager_required
def collateral_edit(request, pk):
    collateral = get_object_or_404(LoanCollateral.objects.select_related('loan'), pk=pk)
    loan = collateral.loan
    branch = getattr(request, 'current_branch', None)
    if branch and not request.user.can_access_all_branches and loan.branch != branch:
        messages.error(request, 'Access denied.')
        return redirect('loans:list')

    if request.method == 'POST':
        form = LoanCollateralForm(request.POST, request.FILES, instance=collateral)
        if form.is_valid():
            form.save()
            messages.success(request, 'Collateral updated.')
            return redirect('loans:detail', pk=loan.pk)
    else:
        form = LoanCollateralForm(instance=collateral)

    return render(request, 'loans/collateral_form.html', {
        'form': form, 'loan': loan, 'title': f'Edit Collateral: {collateral.get_collateral_type_display()}',
    })


@manager_required
def collateral_delete(request, pk):
    collateral = get_object_or_404(LoanCollateral.objects.select_related('loan'), pk=pk)
    loan = collateral.loan
    branch = getattr(request, 'current_branch', None)
    if branch and not request.user.can_access_all_branches and loan.branch != branch:
        messages.error(request, 'Access denied.')
        return redirect('loans:list')
    if loan.status in ('closed', 'rejected', 'written_off'):
        messages.error(request, 'Cannot modify collateral on this loan.')
        return redirect('loans:detail', pk=loan.pk)

    if request.method != 'POST':
        return redirect('loans:detail', pk=loan.pk)

    desc = collateral.get_collateral_type_display()
    collateral.delete()
    messages.success(request, f'{desc} collateral removed.')
    return redirect('loans:detail', pk=loan.pk)


@auditor_or_above
def loan_ledger(request, pk):
    from decimal import Decimal

    from .models import StandingInstruction

    loan = get_object_or_404(
        LoanAccount.objects.select_related('member', 'loan_product', 'branch'),
        pk=pk,
    )
    if not request.user.can_access_all_branches and loan.branch != request.current_branch:
        messages.error(request, 'You do not have access to this loan.')
        return redirect('loans:list')

    entries = []
    running_balance = Decimal('0')

    if loan.disbursed_date and loan.disbursed_amount:
        running_balance = loan.disbursed_amount
        entries.append({
            'date': loan.disbursed_date,
            'type': 'Disbursement',
            'debit': loan.disbursed_amount,
            'credit': Decimal('0'),
            'balance': running_balance,
            'narration': f'Loan disbursed — {loan.loan_product.name}',
            'receipt': '',
        })

    repayments = LoanRepayment.objects.filter(loan=loan).order_by('payment_date', 'pk')
    charges = StandingInstruction.objects.filter(loan=loan).order_by('charge_date', 'pk')

    repayment_list = list(repayments)
    charge_list = list(charges)

    ri, ci = 0, 0
    while ri < len(repayment_list) or ci < len(charge_list):
        pick_charge = False
        if ri >= len(repayment_list):
            pick_charge = True
        elif ci < len(charge_list):
            if charge_list[ci].charge_date < repayment_list[ri].payment_date:
                pick_charge = True

        if pick_charge:
            c = charge_list[ci]
            running_balance += c.amount
            entries.append({
                'date': c.charge_date,
                'type': c.get_charge_type_display(),
                'debit': c.amount,
                'credit': Decimal('0'),
                'balance': running_balance,
                'narration': c.narration or c.get_charge_type_display(),
                'receipt': '',
            })
            ci += 1
        else:
            r = repayment_list[ri]
            running_balance -= r.amount
            entries.append({
                'date': r.payment_date,
                'type': 'Repayment',
                'debit': Decimal('0'),
                'credit': r.amount,
                'balance': running_balance,
                'narration': f'Principal: {r.principal_adjusted}, Interest: {r.interest_adjusted}',
                'receipt': r.receipt_no,
            })
            ri += 1

    return render(request, 'loans/ledger.html', {
        'loan': loan,
        'entries': entries,
        'running_balance': running_balance,
    })


@manager_required
@day_open_required
def loan_reverse_repayment(request, pk, repayment_id):
    from .models import LoanRepayment
    from .services import reverse_repayment

    loan = get_object_or_404(LoanAccount, pk=pk)
    repayment = get_object_or_404(LoanRepayment, pk=repayment_id, loan=loan)

    if request.method == 'POST':
        try:
            reverse_repayment(repayment, request.user)
            messages.success(request, f'Repayment {repayment.receipt_no} cancelled successfully.')
        except ValueError as e:
            messages.error(request, str(e))
        return redirect('loans:detail', pk=pk)

    return render(request, 'loans/reverse_repayment.html', {'loan': loan, 'repayment': repayment})
