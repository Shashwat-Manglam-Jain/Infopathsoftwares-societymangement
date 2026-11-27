from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction as db_transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.accounts.permissions import (
    AuditorOrAboveMixin,
    admin_required,
    auditor_or_above,
    cashier_required,
    day_open_required,
    has_branch_access,
    manager_required,
)
from apps.core.account_utils import amount_to_words as _amount_to_words

from . import services
from .forms import SharePurchaseForm, ShareSurrenderForm, ShareTransferForm
from .models import ShareConfig, ShareHolding, ShareTransaction


@auditor_or_above
def share_list(request):
    holdings = ShareHolding.objects.filter(status='active').select_related('member', 'branch')
    if not request.user.can_access_all_branches:
        holdings = holdings.filter(branch=request.current_branch)
    q = request.GET.get('q', '').strip()
    if q:
        from django.db import models as db_models

        holdings = holdings.filter(
            db_models.Q(member__name__icontains=q)
            | db_models.Q(member__member_no__icontains=q)
            | db_models.Q(certificate_no__icontains=q)
        )

    dividend_results = None
    total_dividend = Decimal('0')
    dividend_count = 0

    if request.method == 'POST' and request.user.is_manager:
        rate_str = request.POST.get('dividend_rate', '')
        financial_year = request.POST.get('financial_year', '')
        try:
            rate = Decimal(rate_str)
            if rate <= 0 or rate > 100:
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            messages.error(request, 'Enter a valid dividend rate (0-100).')
            return render(request, 'shares/list.html', {'holdings': holdings})

        branch = request.current_branch if not request.user.can_access_all_branches else None
        dividend_results = services.calculate_dividend(rate, financial_year, branch=branch)
        total_dividend = sum(r['dividend'] for r in dividend_results)
        dividend_count = len(dividend_results)

        if 'confirm' in request.POST:
            from apps.savings.models import AccountTransaction, SavingsAccount

            posted = 0
            from apps.core.date_utils import get_transaction_date

            today = get_transaction_date(request.current_branch)
            with db_transaction.atomic():
                existing_dividend = (
                    ShareTransaction.objects.select_for_update()
                    .filter(
                        txn_type='dividend',
                        narration=f'Dividend @ {rate}% for FY {financial_year}',
                    )
                    .exists()
                )
                if existing_dividend:
                    messages.error(request, f'Dividend for FY {financial_year} has already been posted.')
                    return redirect('shares:list')
                total_dividend_posted = Decimal('0')
                dividend_branch = request.current_branch or (
                    dividend_results[0]['holding'].branch if dividend_results else None
                )
                for r in dividend_results:
                    member = r['member']
                    holding = r.get('holding')
                    savings = (
                        SavingsAccount.objects.select_for_update()
                        .filter(
                            member=member,
                            status='active',
                        )
                        .first()
                    )
                    if savings:
                        savings.current_balance += r['dividend']
                        savings.save(update_fields=['current_balance'])
                        AccountTransaction.objects.create(
                            account=savings,
                            branch=savings.branch,
                            txn_date=today,
                            value_date=today,
                            txn_type='dividend',
                            amount=r['dividend'],
                            running_balance=savings.current_balance,
                            narration=f'Dividend @ {rate}% for FY {financial_year}',
                            payment_mode='transfer',
                            created_by=request.user,
                        )
                        if holding:
                            ShareTransaction.objects.create(
                                member=member,
                                branch=holding.branch,
                                txn_type='dividend',
                                shares_count=0,
                                amount=r['dividend'],
                                txn_date=today,
                                narration=f'Dividend @ {rate}% for FY {financial_year}',
                                created_by=request.user,
                            )
                        total_dividend_posted += r['dividend']
                        posted += 1

                if total_dividend_posted > 0 and dividend_branch:
                    from apps.accounting.services import create_journal_entry
                    from apps.core.gl_utils import get_gl_code

                    savings_code = get_gl_code('saving', '2001')
                    share_code = get_gl_code('shares', '2501')
                    create_journal_entry(
                        entry_date=today,
                        voucher_type='journal',
                        branch=dividend_branch,
                        narration=f'Dividend @ {rate}% for FY {financial_year}',
                        lines=[
                            {'account_code': share_code, 'debit': total_dividend_posted, 'credit': Decimal('0')},
                            {'account_code': savings_code, 'debit': Decimal('0'), 'credit': total_dividend_posted},
                        ],
                        user=request.user,
                        reference_type='dividend',
                        is_posted=True,
                    )

            messages.success(request, f'Dividend posted to {posted} accounts. Total: ₹{total_dividend:,.2f}')
            return redirect('shares:list')

    paginator = Paginator(holdings, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(
        request,
        'shares/list.html',
        {
            'holdings': page_obj,
            'dividend_results': dividend_results,
            'total_dividend': total_dividend,
            'dividend_count': dividend_count,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'paginator': paginator,
        },
    )


@cashier_required
@day_open_required
def share_purchase(request):
    if request.current_branch is None:
        messages.warning(request, 'Please select a specific branch before purchasing shares.')
        return redirect('shares:list')
    if request.method == 'POST':
        form = SharePurchaseForm(request.POST)
        if form.is_valid():
            try:
                holding = services.purchase_shares(
                    member=form.cleaned_data['member'],
                    branch=request.current_branch,
                    count=form.cleaned_data['share_count'],
                    user=request.user,
                )
                messages.success(
                    request, f'{holding.share_count} shares purchased for {form.cleaned_data["member"].name}.'
                )
                return redirect('shares:list')
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = SharePurchaseForm()

    if not request.user.can_access_all_branches:
        from apps.members.models import Member

        form.fields['member'].queryset = Member.objects.filter(
            branch=request.current_branch,
            status='active',
        )

    config = ShareConfig.objects.filter(is_active=True).first()
    total_shareholders = ShareHolding.objects.filter(status='active', share_count__gt=0).count()
    return render(
        request,
        'shares/purchase.html',
        {
            'form': form,
            'config': config,
            'total_shareholders': total_shareholders,
        },
    )


@cashier_required
def share_member_info(request, member_id):
    from apps.members.models import Member

    member = get_object_or_404(Member, pk=member_id, status='active')
    holding = ShareHolding.objects.filter(member=member, status='active').first()
    config = ShareConfig.objects.filter(is_active=True).first()
    max_allowed = config.max_shares_per_member if config else 0
    current = holding.share_count if holding else 0
    return JsonResponse(
        {
            'name': member.name,
            'member_no': member.member_no,
            'current_shares': current,
            'current_amount': float(holding.total_amount) if holding else 0,
            'remaining_capacity': max(0, max_allowed - current),
            'max_shares': max_allowed,
        }
    )


@manager_required
@day_open_required
def share_transfer(request):
    if request.method == 'POST':
        form = ShareTransferForm(request.POST)
        if form.is_valid():
            try:
                services.transfer_shares(
                    from_member=form.cleaned_data['from_member'],
                    to_member=form.cleaned_data['to_member'],
                    count=form.cleaned_data['share_count'],
                    user=request.user,
                )
                messages.success(request, f'{form.cleaned_data["share_count"]} shares transferred.')
                return redirect('shares:list')
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = ShareTransferForm()

    if not request.user.can_access_all_branches:
        from apps.members.models import Member

        branch_members = Member.objects.filter(branch=request.current_branch, status='active')
        form.fields['from_member'].queryset = branch_members
        form.fields['to_member'].queryset = branch_members

    return render(request, 'shares/transfer.html', {'form': form})


@manager_required
@day_open_required
def share_surrender(request):
    if request.method == 'POST':
        form = ShareSurrenderForm(request.POST)
        if form.is_valid():
            try:
                services.surrender_shares(
                    member=form.cleaned_data['member'],
                    count=form.cleaned_data['share_count'],
                    user=request.user,
                )
                messages.success(request, f'{form.cleaned_data["share_count"]} shares surrendered.')
                return redirect('shares:list')
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = ShareSurrenderForm()

    if not request.user.can_access_all_branches:
        from apps.members.models import Member

        form.fields['member'].queryset = Member.objects.filter(
            branch=request.current_branch,
            status='active',
        )

    return render(request, 'shares/surrender.html', {'form': form})


@auditor_or_above
def share_detail(request, pk):
    holding = get_object_or_404(
        ShareHolding.objects.select_related('member', 'branch'),
        pk=pk,
    )
    if not has_branch_access(request, holding.branch):
        messages.error(request, 'You do not have access to this holding.')
        return redirect('shares:list')
    transactions = ShareTransaction.objects.filter(member=holding.member).order_by('-txn_date')[:20]
    dividends = ShareTransaction.objects.filter(member=holding.member, txn_type='dividend').order_by('-txn_date')
    config = ShareConfig.objects.filter(is_active=True).first()
    return render(
        request,
        'shares/detail.html',
        {
            'holding': holding,
            'transactions': transactions,
            'dividends': dividends,
            'config': config,
        },
    )


class ShareReceiptView(AuditorOrAboveMixin, View):
    def get(self, request, txn_id):
        txn = get_object_or_404(
            ShareTransaction.objects.select_related(
                'member',
                'branch',
                'created_by',
                'transfer_to_member',
            ),
            id=txn_id,
        )
        if not has_branch_access(request, txn.branch):
            messages.error(request, 'You do not have access to this receipt.')
            return redirect('shares:list')
        holding = ShareHolding.objects.filter(member=txn.member, status='active').first()
        return render(
            request,
            'receipts/share_receipt.html',
            {
                'txn': txn,
                'amount_words': _amount_to_words(txn.amount),
                'face_value': txn.amount / txn.shares_count if txn.shares_count else txn.amount,
                'certificate_no': holding.certificate_no if holding else '',
            },
        )


@admin_required
def share_config(request):
    config = ShareConfig.objects.first()
    if request.method == 'POST':
        try:
            fv = Decimal(request.POST.get('face_value_per_share', '10'))
            max_s = int(request.POST.get('max_shares_per_member', '100'))
            min_s = int(request.POST.get('min_shares_required', '1'))
            if fv <= 0:
                raise ValueError('Face value must be greater than zero.')
            if min_s < 1:
                raise ValueError('Minimum shares must be at least 1.')
            if max_s < min_s:
                raise ValueError('Maximum shares cannot be less than minimum.')
            if config:
                config.face_value_per_share = fv
                config.max_shares_per_member = max_s
                config.min_shares_required = min_s
                config.is_active = True
                config.save()
            else:
                config = ShareConfig.objects.create(
                    name='Default',
                    face_value_per_share=fv,
                    max_shares_per_member=max_s,
                    min_shares_required=min_s,
                    is_active=True,
                )
            messages.success(request, 'Share configuration saved.')
            return redirect('shares:config')
        except (ValueError, InvalidOperation) as e:
            messages.error(request, str(e))
    from django.db.models import Sum

    total_shareholders = ShareHolding.objects.filter(status='active', share_count__gt=0).count()
    total_shares_issued = (
        ShareHolding.objects.filter(status='active').aggregate(
            total=Sum('share_count'),
        )['total']
        or 0
    )
    total_share_capital = ShareHolding.objects.filter(status='active').aggregate(
        total=Sum('total_amount'),
    )['total'] or Decimal('0')
    return render(
        request,
        'shares/config_form.html',
        {
            'config': config,
            'total_shareholders': total_shareholders,
            'total_shares_issued': total_shares_issued,
            'total_share_capital': total_share_capital,
        },
    )
