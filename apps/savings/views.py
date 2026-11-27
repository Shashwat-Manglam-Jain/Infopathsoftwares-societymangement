from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.accounting.models import ChartOfAccounts, InterestMaster
from apps.accounts.permissions import (
    AuditorOrAboveMixin,
    auditor_or_above,
    cashier_required,
    day_open_required,
    has_branch_access,
    manager_required,
)
from apps.core.account_utils import amount_to_words as _amount_to_words
from apps.core.date_utils import get_transaction_date
from apps.members.models import Member

from . import services
from .forms import DepositForm, SavingsAccountEditForm, SavingsAccountForm, WithdrawalForm
from .models import AccountTransaction, SavingsAccount

_ACCOUNT_TYPE_MAP = {'savings': 'saving', 'current': 'current', 'security': 'security'}


def _apply_interest_rate(account):
    head = account.gl_head
    if not head:
        related = _ACCOUNT_TYPE_MAP.get(account.account_type, '')
        if related:
            head = ChartOfAccounts.objects.filter(related_table_name=related, is_active=True).first()
    if head:
        slab = InterestMaster.objects.filter(account_head=head, is_active=True).first()
        if slab:
            account.interest_rate = slab.interest_rate


@auditor_or_above
def savings_list(request):
    account_type = request.GET.get('type', '')
    accounts = SavingsAccount.objects.select_related('member', 'branch', 'gl_head')
    if account_type in ('savings', 'current', 'security'):
        accounts = accounts.filter(account_type=account_type)
    q = request.GET.get('q', '').strip()
    if q:
        accounts = accounts.filter(
            Q(account_no__icontains=q) | Q(member__name__icontains=q) | Q(member__member_no__icontains=q)
        )
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
            'status_filter': status_filter,
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
            account.created_by = request.user
            if not account.branch_id and request.current_branch:
                account.branch = request.current_branch
            _apply_interest_rate(account)
            account.save()
            messages.success(request, f'Savings account {account.account_no} created successfully.')
            return redirect('savings:detail', pk=account.pk)
    else:
        from apps.core.date_utils import get_transaction_date

        initial = {'opening_date': get_transaction_date(request.current_branch).isoformat()}
        account_type = request.GET.get('type', '')
        if account_type:
            related = _ACCOUNT_TYPE_MAP.get(account_type, account_type)
            head = ChartOfAccounts.objects.filter(
                related_table_name=related, allow_transactions=True, is_active=True
            ).first()
            if head:
                initial['gl_head'] = head.pk
        form = SavingsAccountForm(initial=initial, current_branch=branch)

    account_type = request.GET.get('type', '')
    if account_type:
        related = _ACCOUNT_TYPE_MAP.get(account_type, account_type)
        from .forms import _get_leaf_heads

        form.fields['gl_head'].queryset = _get_leaf_heads((related,))

    if branch:
        form.fields['member'].queryset = Member.objects.filter(
            branch=request.current_branch,
            status='active',
        )

    type_labels = {'savings': 'Savings Account', 'current': 'Current Account', 'security': 'Security Deposit'}
    create_title = type_labels.get(account_type, 'Account')
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
            _apply_interest_rate(acct)
            if acct.status == 'closed' and not acct.closing_date:
                acct.closing_date = get_transaction_date(request.current_branch)
            acct.save()
            messages.success(request, f'Account {account.account_no} updated successfully.')
            return redirect('savings:detail', pk=pk)
    else:
        form = SavingsAccountEditForm(instance=account)

    return render(request, 'savings/edit.html', {'form': form, 'account': account})


@auditor_or_above
def savings_detail(request, pk):
    account = get_object_or_404(
        SavingsAccount.objects.select_related('member', 'branch', 'created_by', 'gl_head'),
        pk=pk,
    )
    if not request.user.can_access_all_branches and account.branch != request.current_branch:
        messages.error(request, 'You do not have access to this account.')
        return redirect('savings:list')

    transactions = account.transactions.select_related('reversal_of', 'created_by').order_by(
        '-txn_date', '-created_at'
    )[:20]

    from apps.accounting.models import JournalLine

    pending_vouchers = (
        JournalLine.objects.filter(
            account_number=account.account_no,
            journal_entry__is_posted=False,
            journal_entry__is_rejected=False,
            journal_entry__is_reversed=False,
        )
        .select_related('journal_entry', 'journal_entry__created_by')
        .order_by('-journal_entry__entry_date')[:20]
    )

    context = {
        'account': account,
        'transactions': transactions,
        'pending_vouchers': pending_vouchers,
    }
    if account.status == 'active':
        from apps.dayend.models import WorkingDay

        branch = getattr(request, 'current_branch', None)
        wd = WorkingDay.objects.filter(branch=branch).order_by('-current_date').first() if branch else None
        context['is_day_open'] = bool(wd and wd.is_day_open)
    return render(request, 'savings/detail.html', context)


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
        else:
            for error in form.errors.values():
                messages.error(request, error[0])
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
            amount = form.cleaned_data['amount']
            if amount > account.current_balance:
                messages.error(
                    request,
                    f'Insufficient balance. Available: ₹{account.current_balance}, Requested: ₹{amount}',
                )
                return redirect('savings:detail', pk=pk)
            try:
                txn = services.withdraw(
                    account=account,
                    amount=amount,
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
        else:
            for error in form.errors.values():
                messages.error(request, error[0])
    return redirect('savings:detail', pk=pk)


@auditor_or_above
def savings_statement(request, pk):
    account = get_object_or_404(
        SavingsAccount.objects.select_related('member', 'branch', 'gl_head'),
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
                account.transactions.select_related('reversal_of')
                .filter(
                    txn_date__gte=fd,
                    txn_date__lte=td,
                    is_reversed=False,
                )
                .order_by('txn_date', 'created_at')
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
            if new_status == 'closed' and account.current_balance != 0:
                messages.error(request, 'Cannot close account with non-zero balance.')
                return redirect('savings:detail', pk=pk)
            old_status = account.status
            account.status = new_status
            if new_status == 'closed':
                account.closing_date = get_transaction_date(request.current_branch)
            account.save(update_fields=['status', 'closing_date', 'updated_at'])
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
        if not has_branch_access(request, txn.branch):
            messages.error(request, 'You do not have access to this receipt.')
            return redirect('savings:list')
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
        if not has_branch_access(request, account.branch):
            messages.error(request, 'You do not have access to this account.')
            return redirect('savings:list')
        transactions = account.transactions.select_related('reversal_of').order_by('txn_date', 'created_at')

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
def member_savings_api(request):
    member_id = request.GET.get('member_id', '')
    if not member_id:
        return JsonResponse({'accounts': []})
    accounts = (
        SavingsAccount.objects.filter(
            member_id=member_id,
            status='active',
        )
        .select_related('gl_head')
        .order_by('account_no')
    )
    return JsonResponse(
        {
            'accounts': [
                {
                    'id': a.pk,
                    'account_no': a.account_no,
                    'type': a.get_account_type_display(),
                    'balance': str(a.current_balance),
                }
                for a in accounts
            ]
        }
    )


@login_required
def account_type_rate_api(request):
    head_id_param = request.GET.get('head_id', '')
    account_type = request.GET.get('type', '')

    rate = 0
    head_id = None
    head_name = ''

    head = None
    if head_id_param:
        head = ChartOfAccounts.objects.filter(pk=head_id_param, is_active=True).first()
    elif account_type:
        type_map = {'savings': 'saving', 'current': 'current', 'security': 'security'}
        related = type_map.get(account_type, '')
        if related:
            head = ChartOfAccounts.objects.filter(related_table_name=related, is_active=True).first()

    if head:
        head_id = head.pk
        head_name = str(head)
        slab = InterestMaster.objects.filter(account_head=head, is_active=True).first()
        if slab:
            rate = float(slab.interest_rate)

    return JsonResponse({'rate': rate, 'account_type': account_type, 'head_id': head_id, 'head_name': head_name})


@manager_required
@day_open_required
def savings_reverse_txn(request, pk, txn_id):
    account = get_object_or_404(SavingsAccount, pk=pk)
    if not has_branch_access(request, account.branch):
        messages.error(request, 'You do not have access to this account.')
        return redirect('savings:list')
    txn = get_object_or_404(AccountTransaction, pk=txn_id, account=account)

    from apps.accounts.permissions import is_date_locked

    branch = getattr(request, 'current_branch', None) or txn.branch
    if is_date_locked(branch, txn.txn_date):
        messages.error(request, 'Day-end has been completed for this date. Transaction cannot be reversed.')
        return redirect('savings:detail', pk=pk)

    if request.method == 'POST':
        try:
            services.reverse_transaction(txn, request.user)
            messages.success(request, f'Transaction {txn.voucher_no or txn_id} reversed successfully.')
        except ValueError as e:
            messages.error(request, str(e))
        return redirect('savings:detail', pk=pk)

    return render(request, 'savings/reverse_txn.html', {'account': account, 'txn': txn})
