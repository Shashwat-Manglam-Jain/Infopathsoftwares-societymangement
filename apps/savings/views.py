from datetime import date, datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.accounting.models import ChartOfAccounts, InterestMaster
from apps.accounts.permissions import (
    AuditorOrAboveMixin,
    auditor_or_above,
    cashier_required,
    day_open_required,
    manager_required,
)
from apps.core.account_utils import amount_to_words as _amount_to_words
from apps.members.models import Member

from . import services
from .forms import DepositForm, SavingsAccountEditForm, SavingsAccountForm, WithdrawalForm
from .models import AccountTransaction, SavingsAccount


@auditor_or_above
def savings_list(request):
    account_type = request.GET.get('type', '')
    accounts = SavingsAccount.objects.select_related('member', 'branch')
    if account_type in ('savings', 'current', 'security'):
        accounts = accounts.filter(account_type=account_type)
    status_filter = request.GET.get('status', 'active')
    if status_filter:
        accounts = accounts.filter(status=status_filter)
    if not request.user.can_access_all_branches:
        accounts = accounts.filter(branch=request.current_branch)
    type_labels = {'savings': 'Savings Accounts', 'current': 'Current Accounts', 'security': 'Security Deposits'}
    paginator = Paginator(accounts, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(
        request,
        'savings/list.html',
        {
            'accounts': page_obj,
            'account_type': account_type,
            'page_title': type_labels.get(account_type, 'All Accounts'),
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'paginator': paginator,
        },
    )


@cashier_required
def savings_create(request):
    branch = request.current_branch if not request.user.can_access_all_branches else None
    if request.method == 'POST':
        form = SavingsAccountForm(request.POST, current_branch=branch)
        if form.is_valid():
            account = form.save(commit=False)
            account.opening_date = date.today()
            account.created_by = request.user
            if not account.branch_id and request.current_branch:
                account.branch = request.current_branch
            type_map = {'savings': 'saving', 'current': 'current', 'security': 'security'}
            related = type_map.get(account.account_type, '')
            if related:
                head = ChartOfAccounts.objects.filter(
                    related_table_name=related, is_active=True,
                ).first()
                if head:
                    slab = InterestMaster.objects.filter(
                        account_head=head, is_active=True,
                    ).first()
                    if slab:
                        account.interest_rate = slab.interest_rate
            account.save()
            messages.success(request, f'Savings account {account.account_no} created successfully.')
            return redirect('savings:detail', pk=account.pk)
    else:
        initial = {}
        account_type = request.GET.get('type', '')
        if account_type in ('savings', 'current', 'security'):
            initial['account_type'] = account_type
        form = SavingsAccountForm(initial=initial, current_branch=branch)

    if branch:
        form.fields['member'].queryset = Member.objects.filter(
            branch=request.current_branch,
            status='active',
        )

    type_labels = {'savings': 'Savings Account', 'current': 'Current Account', 'security': 'Security Deposit'}
    create_title = type_labels.get(request.GET.get('type', ''), 'Account')
    return render(request, 'savings/create.html', {'form': form, 'create_title': create_title})


@manager_required
def savings_edit(request, pk):
    account = get_object_or_404(SavingsAccount, pk=pk)
    if not request.user.can_access_all_branches and account.branch != request.current_branch:
        messages.error(request, 'You do not have access to this account.')
        return redirect('savings:list')
    if account.status == 'closed':
        messages.error(request, 'Cannot edit a closed account.')
        return redirect('savings:detail', pk=pk)

    if request.method == 'POST':
        form = SavingsAccountEditForm(request.POST, instance=account)
        if form.is_valid():
            acct = form.save(commit=False)
            # Server-side enforce interest_rate from InterestMaster slab
            type_map = {'savings': 'saving', 'current': 'current', 'security': 'security'}
            related = type_map.get(acct.account_type, '')
            if related:
                head = ChartOfAccounts.objects.filter(
                    related_table_name=related, is_active=True,
                ).first()
                if head:
                    slab = InterestMaster.objects.filter(
                        account_head=head, is_active=True,
                    ).first()
                    if slab:
                        acct.interest_rate = slab.interest_rate
            acct.save()
            messages.success(request, f'Account {account.account_no} updated successfully.')
            return redirect('savings:detail', pk=pk)
    else:
        form = SavingsAccountEditForm(instance=account)

    return render(request, 'savings/edit.html', {'form': form, 'account': account})


@auditor_or_above
def savings_detail(request, pk):
    account = get_object_or_404(
        SavingsAccount.objects.select_related('member', 'branch', 'created_by'),
        pk=pk,
    )
    if not request.user.can_access_all_branches and account.branch != request.current_branch:
        messages.error(request, 'You do not have access to this account.')
        return redirect('savings:list')

    transactions = account.transactions.order_by('-txn_date', '-created_at')[:20]
    deposit_form = DepositForm(initial={'account_id': account.pk})
    withdrawal_form = WithdrawalForm(initial={'account_id': account.pk})
    return render(
        request,
        'savings/detail.html',
        {
            'account': account,
            'transactions': transactions,
            'deposit_form': deposit_form,
            'withdrawal_form': withdrawal_form,
        },
    )


@cashier_required
@day_open_required
def savings_deposit(request, pk):
    account = get_object_or_404(SavingsAccount, pk=pk)
    if not request.user.can_access_all_branches and account.branch != request.current_branch:
        messages.error(request, 'You do not have access to this account.')
        return redirect('savings:list')

    if request.method == 'POST':
        form = DepositForm(request.POST)
        if form.is_valid():
            try:
                txn = services.deposit(
                    account=account,
                    amount=form.cleaned_data['amount'],
                    branch=account.branch,
                    user=request.user,
                    payment_mode=form.cleaned_data['payment_mode'],
                    narration=form.cleaned_data.get('narration', ''),
                    cheque_no=form.cleaned_data.get('cheque_no'),
                    cheque_date=form.cleaned_data.get('cheque_date'),
                    bank_name=form.cleaned_data.get('bank_name'),
                )
                messages.success(
                    request,
                    f'Deposit of ₹{txn.amount} successful. Receipt: {txn.receipt_no}',
                )
            except ValueError as e:
                messages.error(request, str(e))
    return redirect('savings:detail', pk=pk)


@cashier_required
@day_open_required
def savings_withdraw(request, pk):
    account = get_object_or_404(SavingsAccount, pk=pk)
    if not request.user.can_access_all_branches and account.branch != request.current_branch:
        messages.error(request, 'You do not have access to this account.')
        return redirect('savings:list')

    if request.method == 'POST':
        form = WithdrawalForm(request.POST)
        if form.is_valid():
            try:
                txn = services.withdraw(
                    account=account,
                    amount=form.cleaned_data['amount'],
                    branch=account.branch,
                    user=request.user,
                    payment_mode=form.cleaned_data['payment_mode'],
                    narration=form.cleaned_data.get('narration', ''),
                )
                messages.success(
                    request,
                    f'Withdrawal of ₹{txn.amount} successful. Receipt: {txn.receipt_no}',
                )
            except ValueError as e:
                messages.error(request, str(e))
    return redirect('savings:detail', pk=pk)


@auditor_or_above
def savings_statement(request, pk):
    account = get_object_or_404(
        SavingsAccount.objects.select_related('member', 'branch'),
        pk=pk,
    )
    if not request.user.can_access_all_branches and account.branch != request.current_branch:
        messages.error(request, 'You do not have access to this account.')
        return redirect('savings:list')

    transactions = []
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')

    if from_date and to_date:
        try:
            fd = datetime.strptime(from_date, '%Y-%m-%d').date()
            td = datetime.strptime(to_date, '%Y-%m-%d').date()
            transactions = list(
                account.transactions.filter(
                    txn_date__gte=fd,
                    txn_date__lte=td,
                ).order_by('txn_date', 'created_at')
            )
        except ValueError:
            messages.error(request, 'Invalid date format.')

    return render(
        request,
        'savings/statement.html',
        {
            'account': account,
            'transactions': transactions,
            'from_date': from_date or '',
            'to_date': to_date or '',
        },
    )


@manager_required
def savings_change_status(request, pk):
    account = get_object_or_404(SavingsAccount, pk=pk)
    if not request.user.can_access_all_branches and account.branch != request.current_branch:
        messages.error(request, 'You do not have access to this account.')
        return redirect('savings:list')

    if request.method == 'POST':
        new_status = request.POST.get('status')
        valid = [c[0] for c in SavingsAccount.STATUS_CHOICES]
        if new_status in valid:
            old_status = account.status
            account.status = new_status
            if new_status == 'closed':
                account.closing_date = date.today()
            account.save()
            messages.success(request, f'Account status changed from {old_status} to {new_status}.')
    return redirect('savings:detail', pk=pk)


class DepositReceiptView(AuditorOrAboveMixin, View):
    def get(self, request, txn_id):
        txn = get_object_or_404(
            AccountTransaction.objects.select_related(
                'account__member__branch',
                'branch',
                'created_by',
            ),
            id=txn_id,
        )
        template = 'receipts/deposit_receipt.html'
        if txn.txn_type == 'withdrawal':
            template = 'receipts/withdrawal_receipt.html'
        return render(
            request,
            template,
            {
                'txn': txn,
                'amount_words': _amount_to_words(txn.amount),
            },
        )


class PassbookPrintView(AuditorOrAboveMixin, View):
    def get(self, request, account_id):
        account = get_object_or_404(
            SavingsAccount.objects.select_related('member', 'branch'),
            id=account_id,
        )
        transactions = account.transactions.order_by('txn_date', 'created_at')

        from_date = request.GET.get('from')
        to_date = request.GET.get('to')
        if from_date:
            try:
                from_date = datetime.strptime(from_date, '%Y-%m-%d').date()
                transactions = transactions.filter(txn_date__gte=from_date)
            except ValueError:
                from_date = None
        if to_date:
            try:
                to_date = datetime.strptime(to_date, '%Y-%m-%d').date()
                transactions = transactions.filter(txn_date__lte=to_date)
            except ValueError:
                to_date = None

        txn_list = list(transactions)
        rows_per_page = 20
        pages = [txn_list[i : i + rows_per_page] for i in range(0, len(txn_list), rows_per_page)] or [[]]

        return render(
            request,
            'receipts/passbook_print.html',
            {
                'account': account,
                'transactions': txn_list,
                'pages': pages,
                'from_date': from_date,
                'to_date': to_date,
            },
        )


@login_required
def account_type_rate_api(request):
    account_type = request.GET.get('type', '')
    type_map = {'savings': 'saving', 'current': 'current', 'security': 'security'}
    related = type_map.get(account_type, '')

    rate = 0
    if related:
        head = ChartOfAccounts.objects.filter(
            related_table_name=related,
            is_active=True,
        ).first()
        if head:
            slab = InterestMaster.objects.filter(
                account_head=head,
                is_active=True,
            ).first()
            if slab:
                rate = float(slab.interest_rate)

    return JsonResponse({'rate': rate, 'account_type': account_type})


@manager_required
@day_open_required
def savings_reverse_txn(request, pk, txn_id):
    account = get_object_or_404(SavingsAccount, pk=pk)
    txn = get_object_or_404(AccountTransaction, pk=txn_id, account=account)

    if request.method == 'POST':
        try:
            services.reverse_transaction(txn, request.user)
            messages.success(request, f'Transaction {txn.voucher_no or txn_id} reversed successfully.')
        except ValueError as e:
            messages.error(request, str(e))
        return redirect('savings:detail', pk=pk)

    return render(request, 'savings/reverse_txn.html', {'account': account, 'txn': txn})
