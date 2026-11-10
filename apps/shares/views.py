from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction as db_transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from apps.accounts.permissions import (
    AuditorOrAboveMixin,
    admin_required,
    auditor_or_above,
    cashier_required,
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

        dividend_results = services.calculate_dividend(rate, financial_year)
        total_dividend = sum(r['dividend'] for r in dividend_results)
        dividend_count = len(dividend_results)

        if 'confirm' in request.POST:
            from apps.savings.models import AccountTransaction, SavingsAccount

            posted = 0
            today = timezone.now().date()
            with db_transaction.atomic():
                for r in dividend_results:
                    member = r['member']
                    savings = SavingsAccount.objects.filter(
                        member=member,
                        status='active',
                    ).first()
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
                        posted += 1

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

    return render(request, 'shares/purchase.html', {'form': form})


@manager_required
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
def share_config_list(request):
    from .models import ShareConfig

    configs = ShareConfig.objects.all()
    return render(request, 'shares/config_list.html', {'configs': configs})


@admin_required
def share_config_create(request):
    from .models import ShareConfig

    if request.method == 'POST':
        try:
            name = request.POST.get('name', '').strip()
            if not name:
                raise ValueError('Name is required.')
            ShareConfig.objects.filter(is_active=True).update(is_active=False)
            ShareConfig.objects.create(
                name=name,
                face_value_per_share=Decimal(request.POST.get('face_value_per_share', '10')),
                max_shares_per_member=int(request.POST.get('max_shares_per_member', '100')),
                min_shares_required=int(request.POST.get('min_shares_required', '1')),
                is_active=True,
            )
            messages.success(request, 'Share configuration created and set as active.')
        except (ValueError, Exception) as e:
            messages.error(request, str(e))
            return render(request, 'shares/config_form.html', {'title': 'New Share Config'})
        return redirect('shares:config_list')
    return render(request, 'shares/config_form.html', {'title': 'New Share Config'})


@admin_required
def share_config_edit(request, pk):
    from .models import ShareConfig

    config = get_object_or_404(ShareConfig, pk=pk)
    if request.method == 'POST':
        try:
            config.name = request.POST.get('name', config.name).strip()
            config.face_value_per_share = Decimal(request.POST.get('face_value_per_share', '10'))
            config.max_shares_per_member = int(request.POST.get('max_shares_per_member', '100'))
            config.min_shares_required = int(request.POST.get('min_shares_required', '1'))
            config.save()
            messages.success(request, 'Share configuration updated.')
        except Exception as e:
            messages.error(request, str(e))
            return render(request, 'shares/config_form.html', {'config': config, 'title': f'Edit: {config.name}'})
        return redirect('shares:config_list')
    return render(request, 'shares/config_form.html', {'config': config, 'title': f'Edit: {config.name}'})


@admin_required
def share_config_toggle(request, pk):
    from .models import ShareConfig

    config = get_object_or_404(ShareConfig, pk=pk)
    if request.method == 'POST':
        if config.is_active:
            config.is_active = False
            config.save(update_fields=['is_active'])
            messages.success(request, f'"{config.name}" disabled.')
        else:
            ShareConfig.objects.filter(is_active=True).update(is_active=False)
            config.is_active = True
            config.save(update_fields=['is_active'])
            messages.success(request, f'"{config.name}" is now the active configuration.')
    return redirect('shares:config_list')
