from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.core.account_utils import amount_to_words as _amount_to_words
from apps.core.account_utils import generate_account_number

from .forms import (
    EMICollectionForm,
    GuarantorFormSet,
    LoanApplicationForm,
    LoanApprovalForm,
    LoanProductForm,
)
from .models import EMISchedule, LoanAccount, LoanProduct, LoanRepayment
from .services import (
    approve_loan,
    collect_emi,
    disburse_loan,
    reject_loan,
    validate_loan_application,
)


@login_required
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
    return render(request, 'loans/list.html', {
        'loans': loans,
        'status_filter': status_filter,
    })


@login_required
def loan_detail(request, pk):
    loan = get_object_or_404(
        LoanAccount.objects.select_related('member', 'loan_product', 'branch', 'director_recommendation'),
        pk=pk,
    )
    if not request.user.can_access_all_branches and loan.branch != request.current_branch:
        messages.error(request, 'You do not have access to this loan.')
        return redirect('loans:list')

    guarantors = loan.guarantors.select_related('guarantor_member').all()
    collaterals = loan.collaterals.all()
    emi_schedule = EMISchedule.objects.filter(loan=loan).order_by('installment_no')
    repayments = LoanRepayment.objects.filter(loan=loan).order_by('-payment_date')[:20]

    approval_form = None
    emi_form = None
    if loan.status == 'applied':
        approval_form = LoanApprovalForm(initial={'approved_amount': loan.applied_amount})
    elif loan.status in ('disbursed', 'npa'):
        emi_form = EMICollectionForm(initial={'loan_id': loan.pk})

    return render(request, 'loans/detail.html', {
        'loan': loan,
        'guarantors': guarantors,
        'collaterals': collaterals,
        'emi_schedule': emi_schedule,
        'repayments': repayments,
        'approval_form': approval_form,
        'emi_form': emi_form,
    })


@login_required
def loan_apply(request):
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
                        loan.loan_no = generate_account_number(request.current_branch, '010')
                        loan.created_by = request.user
                        loan.save()

                        guarantor_formset = GuarantorFormSet(
                            request.POST, prefix='guarantors', instance=loan,
                        )
                        if guarantor_formset.is_valid():
                            guarantor_formset.save()

                    messages.success(request, f'Loan application {loan.loan_no} submitted.')
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

    return render(request, 'loans/apply.html', {
        'form': form,
        'guarantor_formset': guarantor_formset,
    })


@login_required
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


@login_required
def loan_disburse(request, pk):
    loan = get_object_or_404(LoanAccount, pk=pk)
    if request.method != 'POST':
        return redirect('loans:detail', pk=pk)

    try:
        disburse_loan(loan, request.current_branch, request.user)
        messages.success(request, f'Loan {loan.loan_no} disbursed. EMI schedule generated.')
    except ValueError as e:
        messages.error(request, str(e))

    return redirect('loans:detail', pk=pk)


@login_required
def loan_collect(request, pk):
    loan = get_object_or_404(LoanAccount, pk=pk)
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


@login_required
def loan_product_list(request):
    products = LoanProduct.objects.all().order_by('name')
    return render(request, 'loans/product_list.html', {'products': products})


@login_required
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


@login_required
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


class EMIReceiptView(LoginRequiredMixin, View):
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
