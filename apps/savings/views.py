from datetime import date, datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.core.account_utils import amount_to_words as _amount_to_words
from apps.members.models import Member

from . import services
from .forms import DepositForm, SavingsAccountForm, WithdrawalForm
from .models import AccountTransaction, SavingsAccount


@login_required
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
    return render(request, 'savings/list.html', {
        'accounts': accounts,
        'account_type': account_type,
        'page_title': type_labels.get(account_type, 'All Accounts'),
    })


@login_required
def savings_create(request):
    if request.method == 'POST':
        form = SavingsAccountForm(request.POST)
        if form.is_valid():
            account = form.save(commit=False)
            account.opening_date = date.today()
            account.created_by = request.user
            account.save()
            messages.success(request, f'Savings account {account.account_no} created successfully.')
            return redirect('savings:detail', pk=account.pk)
    else:
        initial = {}
        account_type = request.GET.get('type', '')
        if account_type in ('savings', 'current', 'security'):
            initial['account_type'] = account_type
        form = SavingsAccountForm(initial=initial)

    if not request.user.can_access_all_branches:
        form.fields['member'].queryset = Member.objects.filter(
            branch=request.current_branch, status='active',
        )
        form.fields['branch'].initial = request.current_branch

    type_labels = {'savings': 'Savings Account', 'current': 'Current Account', 'security': 'Security Deposit'}
    create_title = type_labels.get(request.GET.get('type', ''), 'Account')
    return render(request, 'savings/create.html', {'form': form, 'create_title': create_title})


@login_required
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
    return render(request, 'savings/detail.html', {
        'account': account,
        'transactions': transactions,
        'deposit_form': deposit_form,
        'withdrawal_form': withdrawal_form,
    })


@login_required
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


@login_required
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


@login_required
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
                    txn_date__gte=fd, txn_date__lte=td,
                ).order_by('txn_date', 'created_at')
            )
        except ValueError:
            messages.error(request, 'Invalid date format.')

    return render(request, 'savings/statement.html', {
        'account': account,
        'transactions': transactions,
        'from_date': from_date or '',
        'to_date': to_date or '',
    })


@login_required
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


class DepositReceiptView(LoginRequiredMixin, View):
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


class PassbookPrintView(LoginRequiredMixin, View):
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
