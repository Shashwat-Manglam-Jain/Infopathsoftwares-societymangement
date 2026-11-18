import csv
from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db import models, transaction
from django.db.models import Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.permissions import (
    accountant_required,
    admin_required,
    auditor_or_above,
    cashier_required,
    day_open_required,
    has_branch_access,
    manager_required,
)
from apps.core.date_utils import get_transaction_date

from .forms import ChartOfAccountsForm, InterestMasterForm, VoucherForm
from .models import ChartOfAccounts, InterestMaster, JournalEntry

CUSTOMER_ACCOUNT_TYPES = ('saving', 'current', 'recurring', 'fixed', 'security', 'loan', 'advance', 'agent', 'client')


@auditor_or_above
def voucher_list(request):
    from django.core.paginator import Paginator

    entries = JournalEntry.objects.select_related('branch', 'created_by')
    if not request.user.can_access_all_branches:
        entries = entries.filter(branch=request.current_branch)
    entries = entries.order_by('-entry_date', '-created_at')
    paginator = Paginator(entries, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(
        request,
        'accounting/vouchers.html',
        {
            'entries': page_obj,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'paginator': paginator,
        },
    )


@cashier_required
@day_open_required
def receipt_transaction(request):
    if request.current_branch is None:
        messages.warning(request, 'Please select a specific branch before creating transactions.')
        return redirect('accounting:vouchers')
    heads = ChartOfAccounts.objects.filter(allow_transactions=True, is_active=True).order_by('code')
    if request.method == 'POST':
        return _process_transaction(request, 'receipt', heads)
    return render(
        request,
        'accounting/transaction.html',
        {
            'heads': heads,
            'txn_type': 'receipt',
            'title': 'Receipt Transaction',
        },
    )


@cashier_required
@day_open_required
def payment_transaction(request):
    if request.current_branch is None:
        messages.warning(request, 'Please select a specific branch before creating transactions.')
        return redirect('accounting:vouchers')
    heads = ChartOfAccounts.objects.filter(allow_transactions=True, is_active=True).order_by('code')
    if request.method == 'POST':
        return _process_transaction(request, 'payment', heads)
    return render(
        request,
        'accounting/transaction.html',
        {
            'heads': heads,
            'txn_type': 'payment',
            'title': 'Payment Transaction',
        },
    )


def _update_personal_account(head, account_number, amount, txn_type, entry_date, branch, user, journal_entry):
    """Update personal account balance when a receipt/payment targets a customer-linked GL head."""
    rt = head.related_table_name

    if rt in ('saving', 'current', 'security'):
        from apps.savings.models import AccountTransaction, SavingsAccount

        try:
            account = SavingsAccount.objects.select_for_update().get(account_no=account_number)
        except SavingsAccount.DoesNotExist:
            return

        if txn_type == 'receipt':
            account.current_balance += amount
            at_type = 'deposit'
        else:
            if account.current_balance - amount < account.minimum_balance:
                raise ValueError(
                    f'Insufficient balance in {account.account_no}. '
                    f'Available: {account.current_balance}, Minimum: {account.minimum_balance}'
                )
            account.current_balance -= amount
            at_type = 'withdrawal'
        account.save(update_fields=['current_balance', 'updated_at'])

        AccountTransaction.objects.create(
            account=account,
            txn_type=at_type,
            amount=amount,
            running_balance=account.current_balance,
            branch=branch,
            narration=f'{txn_type.title()} voucher {journal_entry.voucher_no}',
            voucher_no=journal_entry.voucher_no,
            txn_date=entry_date,
            value_date=entry_date,
            created_by=user,
        )

    elif rt in ('loan', 'advance'):
        from apps.loans.models import LoanAccount, LoanRepayment

        try:
            loan = LoanAccount.objects.select_for_update().get(loan_no=account_number)
        except LoanAccount.DoesNotExist:
            return

        if txn_type == 'receipt':
            loan.outstanding_principal = max(loan.outstanding_principal - amount, Decimal('0'))
            loan.save(update_fields=['outstanding_principal', 'updated_at'])
            LoanRepayment.objects.create(
                loan=loan,
                branch=branch,
                payment_date=entry_date,
                amount=amount,
                principal_adjusted=amount,
                interest_adjusted=Decimal('0'),
                receipt_no=journal_entry.voucher_no,
                created_by=user,
            )
        else:
            loan.outstanding_principal += amount
            loan.save(update_fields=['outstanding_principal', 'updated_at'])


def _process_transaction(request, txn_type, heads):
    from apps.accounting.services import create_journal_entry
    from apps.accounts.permissions import is_date_locked

    entry_date_str = request.POST.get('entry_date', '')
    narration = request.POST.get('narration', '')
    raw_mode = request.POST.get('payment_mode', 'cash')
    payment_mode = 'cash' if raw_mode == 'cash' else 'transfer'
    try:
        total_forms = int(request.POST.get('lines-TOTAL_FORMS', 0))
    except (ValueError, TypeError):
        total_forms = 0

    try:
        entry_date = date.fromisoformat(entry_date_str)
    except (ValueError, TypeError):
        entry_date = date.today()

    if is_date_locked(request.current_branch, entry_date):
        messages.error(request, 'Day-end has been completed for this date. No transactions allowed.')
        title = 'Receipt Transaction' if txn_type == 'receipt' else 'Payment Transaction'
        return render(
            request,
            'accounting/transaction.html',
            {'heads': heads, 'txn_type': txn_type, 'title': title},
        )

    lines = []
    line_heads = []
    total_amount = Decimal('0')
    for i in range(total_forms):
        gl_id = request.POST.get(f'lines-{i}-gl_account')
        amount_str = request.POST.get(f'lines-{i}-amount', '0')
        desc = request.POST.get(f'lines-{i}-description', '')
        account_number = request.POST.get(f'lines-{i}-account_number', '').strip()
        if not gl_id or not amount_str:
            continue
        try:
            head = ChartOfAccounts.objects.get(id=int(gl_id))
            amount = Decimal(amount_str)
        except (ChartOfAccounts.DoesNotExist, InvalidOperation, ValueError):
            continue
        if amount <= 0:
            continue

        if txn_type == 'receipt':
            lines.append({'account_code': head.code, 'debit': Decimal('0'), 'credit': amount, 'narration': desc})
        else:
            lines.append({'account_code': head.code, 'debit': amount, 'credit': Decimal('0'), 'narration': desc})
        line_heads.append({'head': head, 'amount': amount, 'account_number': account_number})
        total_amount += amount

    if not lines:
        messages.error(request, 'No valid line items.')
        title = 'Receipt Transaction' if txn_type == 'receipt' else 'Payment Transaction'
        return render(
            request,
            'accounting/transaction.html',
            {
                'heads': heads,
                'txn_type': txn_type,
                'title': title,
            },
        )

    from apps.core.gl_utils import get_cash_code

    cash_code = get_cash_code(request.current_branch)
    cash_head = ChartOfAccounts.objects.filter(code=cash_code).first()
    if not cash_head:
        messages.error(request, 'Cash account head not found. Create it in Chart of Accounts first.')
        title = 'Receipt Transaction' if txn_type == 'receipt' else 'Payment Transaction'
        return render(
            request,
            'accounting/transaction.html',
            {
                'heads': heads,
                'txn_type': txn_type,
                'title': title,
            },
        )

    if txn_type == 'receipt':
        lines.append({'account_code': cash_head.code, 'debit': total_amount, 'credit': Decimal('0')})
    else:
        lines.append({'account_code': cash_head.code, 'debit': Decimal('0'), 'credit': total_amount})

    if txn_type == 'payment' and request.current_branch:
        from apps.accounting.models import CashbookMaster

        today_cb = CashbookMaster.objects.filter(
            txn_date=entry_date,
            branch=request.current_branch,
        ).first()
        if today_cb and today_cb.closing_balance < total_amount:
            messages.warning(
                request,
                f'Warning: Payment of ₹{total_amount} exceeds available cash balance (₹{today_cb.closing_balance}).',
            )

    try:
        branch = request.current_branch
        with transaction.atomic():
            entry = create_journal_entry(
                entry_date=entry_date,
                voucher_type=txn_type,
                branch=branch,
                narration=narration,
                lines=lines,
                user=request.user,
                payment_mode=payment_mode,
            )
            for lh in line_heads:
                if lh['account_number'] and lh['head'].related_table_name in CUSTOMER_ACCOUNT_TYPES:
                    _update_personal_account(
                        head=lh['head'],
                        account_number=lh['account_number'],
                        amount=lh['amount'],
                        txn_type=txn_type,
                        entry_date=entry_date,
                        branch=branch,
                        user=request.user,
                        journal_entry=entry,
                    )
            from apps.accounting.services import update_cashbook

            if txn_type == 'receipt':
                update_cashbook(branch, entry_date, receipt_amount=total_amount, payment_mode=payment_mode)
            else:
                update_cashbook(branch, entry_date, payment_amount=total_amount, payment_mode=payment_mode)
        messages.success(request, f'{txn_type.title()} {entry.voucher_no} saved.')
        return redirect('accounting:cashbook')
    except ValueError as e:
        messages.error(request, str(e))
        title = 'Receipt Transaction' if txn_type == 'receipt' else 'Payment Transaction'
        return render(
            request,
            'accounting/transaction.html',
            {
                'heads': heads,
                'txn_type': txn_type,
                'title': title,
            },
        )


@accountant_required
def cashbook_entry(request):
    heads = ChartOfAccounts.objects.filter(allow_transactions=True, is_active=True).order_by('name')

    cb_date = request.GET.get('date')
    if cb_date:
        try:
            cb_date = date.fromisoformat(cb_date)
        except ValueError:
            cb_date = date.today()
    else:
        cb_date = date.today()

    today_entries = (
        JournalEntry.objects.filter(
            entry_date=cb_date,
            voucher_type__in=['receipt', 'payment'],
            is_reversed=False,
        )
        .prefetch_related('lines__gl_account')
        .select_related('created_by')
    )
    if not request.user.can_access_all_branches:
        today_entries = today_entries.filter(branch=request.current_branch)
    today_entries = today_entries.order_by('voucher_type', '-created_at')

    from .models import CashbookMaster

    receipts = today_entries.filter(voucher_type='receipt')
    payments = today_entries.filter(voucher_type='payment')

    receipt_cash = receipts.filter(payment_mode='cash').aggregate(
        total=Sum('lines__credit_amount'),
    )['total'] or Decimal('0')
    receipt_transfer = receipts.filter(payment_mode='transfer').aggregate(
        total=Sum('lines__credit_amount'),
    )['total'] or Decimal('0')
    receipt_total = receipt_cash + receipt_transfer

    payment_cash = payments.filter(payment_mode='cash').aggregate(
        total=Sum('lines__debit_amount'),
    )['total'] or Decimal('0')
    payment_transfer = payments.filter(payment_mode='transfer').aggregate(
        total=Sum('lines__debit_amount'),
    )['total'] or Decimal('0')
    payment_total = payment_cash + payment_transfer

    branch_filter = {}
    if not request.user.can_access_all_branches and request.current_branch:
        branch_filter['branch'] = request.current_branch
    prev_cb = (
        CashbookMaster.objects.filter(
            txn_date__lt=cb_date,
            **branch_filter,
        )
        .order_by('-txn_date')
        .first()
    )
    if prev_cb:
        opening_cash = prev_cb.closing_balance
    else:
        from apps.core.gl_utils import get_cash_code

        branch = getattr(request, 'current_branch', None)
        cash_code = get_cash_code(branch)
        cash_head = ChartOfAccounts.objects.filter(code=cash_code).first()
        opening_cash = cash_head.opening_balance if cash_head else Decimal('0')
    closing_cash = opening_cash + receipt_cash - payment_cash

    context = {
        'heads': heads,
        'today_entries': today_entries,
        'total_receipts': receipt_total,
        'total_payments': payment_total,
        'receipt_cash': receipt_cash,
        'receipt_transfer': receipt_transfer,
        'payment_cash': payment_cash,
        'payment_transfer': payment_transfer,
        'opening_cash': opening_cash,
        'closing_cash': closing_cash,
        'cash_in_hand': receipt_total - payment_total,
        'cb_date': cb_date,
        'today': date.today(),
    }

    if request.GET.get('format') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="cashbook_{cb_date}.csv"'
        writer = csv.writer(response)
        writer.writerow(['Voucher No', 'Type', 'Date', 'Narration', 'Mode', 'Amount'])
        for entry in today_entries:
            total = sum(line.debit_amount for line in entry.lines.all())
            writer.writerow(
                [
                    entry.voucher_no,
                    entry.get_voucher_type_display(),
                    entry.entry_date,
                    entry.narration,
                    entry.get_payment_mode_display(),
                    total,
                ]
            )
        writer.writerow([])
        writer.writerow(['Summary', 'Cash', 'Transfer', 'Total'])
        writer.writerow(['Receipts', receipt_cash, receipt_transfer, receipt_total])
        writer.writerow(['Payments', payment_cash, payment_transfer, payment_total])
        writer.writerow(['Opening Cash', opening_cash])
        writer.writerow(['Closing Cash', closing_cash])
        return response

    return render(request, 'accounting/cashbook.html', context)


@accountant_required
@day_open_required
def voucher_create(request):
    if request.current_branch is None:
        messages.warning(request, 'Please select a specific branch before creating vouchers.')
        return redirect('accounting:vouchers')
    if request.method == 'POST':
        form = VoucherForm(request.POST)
        if form.is_valid():
            from apps.accounting.services import create_journal_entry

            amount = form.cleaned_data['amount']
            try:
                branch = request.current_branch
                entry = create_journal_entry(
                    entry_date=get_transaction_date(branch),
                    voucher_type=form.cleaned_data['voucher_type'],
                    branch=branch,
                    narration=form.cleaned_data['narration'],
                    lines=[
                        {
                            'account_code': form.cleaned_data['debit_account'].code,
                            'debit': amount,
                            'credit': Decimal('0'),
                        },
                        {
                            'account_code': form.cleaned_data['credit_account'].code,
                            'debit': Decimal('0'),
                            'credit': amount,
                        },
                    ],
                    user=request.user,
                )
                messages.success(request, f'Voucher {entry.voucher_no} created.')
                return redirect('accounting:vouchers')
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = VoucherForm()
    return render(request, 'accounting/voucher_create.html', {'form': form})


@auditor_or_above
def chart_of_accounts_list(request):
    heads = ChartOfAccounts.objects.filter(is_active=True).order_by('display_order', 'code')
    heads_by_id = {h.id: h for h in heads}
    children_map = {}
    roots = []
    for head in heads:
        if head.parent_id and head.parent_id in heads_by_id:
            children_map.setdefault(head.parent_id, []).append(head)
        else:
            roots.append(head)

    def build_tree(node_list, depth=0, ancestors=None):
        if ancestors is None:
            ancestors = []
        result = []
        for node in node_list:
            has_children = node.id in children_map
            result.append(
                {
                    'head': node,
                    'depth': depth,
                    'has_children': has_children,
                    'ancestors': list(ancestors),
                }
            )
            if has_children:
                result.extend(build_tree(children_map[node.id], depth + 1, ancestors + [node.id]))
        return result

    groups = {}
    for head in roots:
        group = head.get_account_group_display()
        groups.setdefault(group, [])
        groups[group].extend(build_tree([head]))
    return render(request, 'accounting/heads_list.html', {'groups': groups, 'total': heads.count()})


@admin_required
def chart_of_accounts_create(request):
    if request.method == 'POST':
        form = ChartOfAccountsForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Account head created.')
            return redirect('accounting:heads')
    else:
        form = ChartOfAccountsForm()
    return render(request, 'accounting/heads_form.html', {'form': form, 'title': 'Create Account Head'})


@admin_required
def chart_of_accounts_edit(request, pk):
    head = get_object_or_404(ChartOfAccounts, pk=pk)
    if request.method == 'POST':
        form = ChartOfAccountsForm(request.POST, instance=head)
        if form.is_valid():
            form.save()
            messages.success(request, 'Account head updated.')
            return redirect('accounting:heads')
    else:
        form = ChartOfAccountsForm(instance=head)
    return render(request, 'accounting/heads_form.html', {'form': form, 'title': f'Edit: {head.name}'})


@auditor_or_above
def general_ledger(request):
    account_code = request.GET.get('account')
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    heads = ChartOfAccounts.objects.filter(
        allow_transactions=True,
        is_active=True,
    ).order_by('code')

    context = {
        'heads': heads,
        'selected_account': account_code,
        'from_date': from_date,
        'to_date': to_date,
    }
    if account_code and from_date and to_date:
        from apps.accounting.services import get_ledger

        branch = None if request.user.can_access_all_branches else request.current_branch
        try:
            result = get_ledger(account_code, from_date, to_date, branch=branch)
            context['result'] = result

            if request.GET.get('format') == 'csv' and result:
                response = HttpResponse(content_type='text/csv')
                response['Content-Disposition'] = (
                    f'attachment; filename="ledger_{account_code}_{from_date}_to_{to_date}.csv"'
                )
                writer = csv.writer(response)
                writer.writerow(['Date', 'Voucher', 'Narration', 'Debit', 'Credit', 'Balance'])
                for txn in result.get('entries', []):
                    writer.writerow(
                        [txn['date'], txn['voucher_no'], txn['narration'], txn['debit'], txn['credit'], txn['balance']]
                    )
                return response

        except ChartOfAccounts.DoesNotExist:
            messages.error(request, 'Account head not found.')

    return render(request, 'accounting/general_ledger.html', context)


@auditor_or_above
def day_book(request):
    book_date = request.GET.get('date')
    if book_date:
        try:
            book_date = date.fromisoformat(book_date)
        except ValueError:
            book_date = date.today()
    else:
        book_date = date.today()

    entries = (
        JournalEntry.objects.filter(
            entry_date=book_date,
            is_reversed=False,
        )
        .prefetch_related('lines__gl_account')
        .select_related('branch', 'created_by')
    )
    if not request.user.can_access_all_branches:
        entries = entries.filter(branch=request.current_branch)
    entries = entries.order_by('voucher_type', 'created_at')

    if request.GET.get('format') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="day_book_{book_date}.csv"'
        writer = csv.writer(response)
        writer.writerow(['Voucher No', 'Type', 'Narration', 'Account', 'Debit', 'Credit', 'Created By'])
        for entry in entries:
            for line in entry.lines.all():
                writer.writerow(
                    [
                        entry.voucher_no,
                        entry.get_voucher_type_display(),
                        entry.narration,
                        line.gl_account.name,
                        line.debit_amount,
                        line.credit_amount,
                        entry.created_by.get_full_name() if entry.created_by else '',
                    ]
                )
        return response

    return render(
        request,
        'accounting/day_book.html',
        {
            'book_date': book_date,
            'entries': entries,
            'today': date.today(),
        },
    )


@auditor_or_above
def interest_master_list(request):
    slabs = InterestMaster.objects.select_related('account_head').order_by('account_head__code', 'min_period')
    grouped = {}
    for slab in slabs:
        key = slab.account_head_id
        if key not in grouped:
            grouped[key] = {'head': slab.account_head, 'slabs': []}
        grouped[key]['slabs'].append(slab)
    return render(request, 'accounting/interest_master_list.html', {'groups': grouped.values(), 'total': slabs.count()})


@admin_required
def interest_master_create(request):
    if request.method == 'POST':
        form = InterestMasterForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Interest slab created.')
            return redirect('accounting:interest_master')
    else:
        initial = {}
        head_id = request.GET.get('head')
        if head_id:
            initial['account_head'] = head_id
        form = InterestMasterForm(initial=initial)
    return render(request, 'accounting/interest_master_form.html', {'form': form, 'title': 'Create Interest Slab'})


@auditor_or_above
def cashbook_report(request):
    from .models import CashbookMaster

    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    branch = None if request.user.can_access_all_branches else request.current_branch

    context = {'from_date': from_date, 'to_date': to_date}
    if from_date and to_date:
        qs = CashbookMaster.objects.filter(
            txn_date__gte=from_date,
            txn_date__lte=to_date,
        ).order_by('txn_date')
        if branch:
            qs = qs.filter(branch=branch)
        context['entries'] = qs
        totals = qs.aggregate(
            total_receipts=Sum('total_receipts'),
            total_payments=Sum('total_payments'),
        )
        context['total_receipts'] = totals['total_receipts'] or 0
        context['total_payments'] = totals['total_payments'] or 0

        if request.GET.get('format') == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="cashbook_summary_{from_date}_to_{to_date}.csv"'
            writer = csv.writer(response)
            writer.writerow(['Date', 'Opening Balance', 'Receipts', 'Payments', 'Closing Balance'])
            for e in qs:
                writer.writerow([e.txn_date, e.opening_balance, e.total_receipts, e.total_payments, e.closing_balance])
            return response

    return render(request, 'accounting/cashbook_report.html', context)


@admin_required
def opening_balance_update(request):
    heads = ChartOfAccounts.objects.filter(
        allow_transactions=True,
        is_active=True,
    ).order_by('display_order', 'code')

    total_debit = sum(h.opening_balance for h in heads if h.opening_balance and h.account_group in ('asset', 'expense'))
    total_credit = sum(
        h.opening_balance for h in heads if h.opening_balance and h.account_group in ('liability', 'income', 'equity')
    )

    if request.method == 'POST':
        head_id = request.POST.get('head_id')
        new_balance = request.POST.get('opening_balance', '').strip()

        if not head_id:
            messages.error(request, 'Please select an account head.')
            return redirect('accounting:opening_balance')
        if not new_balance:
            messages.error(request, 'Please enter an opening balance amount.')
            return redirect('accounting:opening_balance')
        try:
            amount = Decimal(new_balance)
        except InvalidOperation:
            messages.error(request, 'Invalid amount. Enter a valid number.')
            return redirect('accounting:opening_balance')
        if amount < 0:
            messages.error(request, 'Opening balance cannot be negative.')
            return redirect('accounting:opening_balance')

        try:
            head = ChartOfAccounts.objects.get(pk=head_id)
        except ChartOfAccounts.DoesNotExist:
            messages.error(request, 'Selected account head not found.')
            return redirect('accounting:opening_balance')

        old_balance = head.opening_balance
        head.opening_balance = amount
        head.save(update_fields=['opening_balance'])

        from apps.audit.services import log_action

        log_action(
            user=request.user,
            branch=getattr(request, 'current_branch', None),
            action='update',
            table_name='ChartOfAccounts',
            record_id=head.pk,
            old_values={'opening_balance': str(old_balance)},
            new_values={'opening_balance': str(amount)},
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        messages.success(
            request,
            f'Opening balance for {head.code} — {head.name} updated: ₹{old_balance} → ₹{amount}',
        )
        return redirect('accounting:opening_balance')

    return render(
        request,
        'accounting/opening_balance.html',
        {
            'heads': heads,
            'total_debit': total_debit,
            'total_credit': total_credit,
            'ob_difference': abs(total_debit - total_credit),
            'ob_balanced': total_debit == total_credit,
        },
    )


@admin_required
def interest_master_edit(request, pk):
    slab = get_object_or_404(InterestMaster, pk=pk)
    if request.method == 'POST':
        form = InterestMasterForm(request.POST, instance=slab)
        if form.is_valid():
            form.save()
            messages.success(request, 'Interest slab updated.')
            return redirect('accounting:interest_master')
    else:
        form = InterestMasterForm(instance=slab)
    return render(request, 'accounting/interest_master_form.html', {'form': form, 'title': f'Edit: {slab}'})


@accountant_required
@day_open_required
def voucher_edit(request, pk):
    if request.current_branch is None:
        messages.warning(request, 'Please select a specific branch before editing vouchers.')
        return redirect('accounting:vouchers')
    entry = get_object_or_404(
        JournalEntry.objects.prefetch_related('lines__gl_account'),
        pk=pk,
    )
    if not has_branch_access(request, entry.branch):
        messages.error(request, 'You do not have access to this voucher.')
        return redirect('accounting:vouchers')
    if entry.is_reversed:
        messages.error(request, 'Cannot edit a reversed voucher.')
        return redirect('accounting:vouchers')
    if entry.entry_date != get_transaction_date(request.current_branch):
        messages.error(request, 'Can only edit vouchers from the current working day.')
        return redirect('accounting:vouchers')

    from apps.accounts.permissions import is_date_locked

    if is_date_locked(request.current_branch, entry.entry_date):
        messages.error(request, 'Day-end has been completed. This voucher cannot be modified.')
        return redirect('accounting:vouchers')

    lines = entry.lines.all()
    debit_line = lines.filter(debit_amount__gt=0).first()
    credit_line = lines.filter(credit_amount__gt=0).first()
    if not debit_line or not credit_line:
        messages.error(request, 'This voucher has complex line structure and cannot be edited from here.')
        return redirect('accounting:vouchers')

    if request.method == 'POST':
        form = VoucherForm(request.POST)
        if form.is_valid():
            from apps.accounting.services import create_journal_entry, reverse_journal_entry, update_cashbook

            try:
                with transaction.atomic():
                    old_amount = debit_line.debit_amount
                    old_type = entry.voucher_type
                    reverse_journal_entry(entry, request.user)
                    if old_type in ('receipt', 'payment'):
                        if old_type == 'receipt':
                            update_cashbook(request.current_branch, entry.entry_date, payment_amount=old_amount)
                        else:
                            update_cashbook(request.current_branch, entry.entry_date, receipt_amount=old_amount)
                    new_amount = form.cleaned_data['amount']
                    new_type = form.cleaned_data['voucher_type']
                    new_entry = create_journal_entry(
                        entry_date=get_transaction_date(request.current_branch),
                        voucher_type=new_type,
                        branch=request.current_branch,
                        narration=form.cleaned_data['narration'],
                        lines=[
                            {
                                'account_code': form.cleaned_data['debit_account'].code,
                                'debit': new_amount,
                                'credit': Decimal('0'),
                            },
                            {
                                'account_code': form.cleaned_data['credit_account'].code,
                                'debit': Decimal('0'),
                                'credit': new_amount,
                            },
                        ],
                        user=request.user,
                        reference_type='modification',
                        reference_id=entry.pk,
                    )
                    if new_type in ('receipt', 'payment'):
                        if new_type == 'receipt':
                            update_cashbook(request.current_branch, new_entry.entry_date, receipt_amount=new_amount)
                        else:
                            update_cashbook(request.current_branch, new_entry.entry_date, payment_amount=new_amount)
                messages.success(request, f'Voucher modified. Old: {entry.voucher_no} → New: {new_entry.voucher_no}')
                return redirect('accounting:vouchers')
            except ValueError as e:
                messages.error(request, str(e))
    else:
        amount = debit_line.debit_amount
        form = VoucherForm(
            initial={
                'voucher_type': entry.voucher_type,
                'narration': entry.narration,
                'debit_account': debit_line.gl_account,
                'credit_account': credit_line.gl_account,
                'amount': amount,
            }
        )

    return render(
        request,
        'accounting/voucher_create.html',
        {
            'form': form,
            'title': f'Modify Voucher: {entry.voucher_no}',
            'is_edit': True,
        },
    )


@manager_required
@day_open_required
def voucher_cancel(request, pk):
    entry = get_object_or_404(
        JournalEntry.objects.prefetch_related('lines__gl_account'),
        pk=pk,
    )
    if not has_branch_access(request, entry.branch):
        messages.error(request, 'You do not have access to this voucher.')
        return redirect('accounting:vouchers')

    from apps.accounts.permissions import is_date_locked

    branch = getattr(request, 'current_branch', None) or entry.branch
    if is_date_locked(branch, entry.entry_date):
        messages.error(request, 'Day-end has been completed. This voucher cannot be cancelled.')
        return redirect('accounting:vouchers')

    if request.method == 'POST':
        if entry.is_reversed:
            messages.error(request, 'This voucher is already reversed/cancelled.')
            return redirect('accounting:vouchers')

        from apps.accounting.services import reverse_journal_entry, update_cashbook

        try:
            with transaction.atomic():
                cancel_amount = sum(line.debit_amount for line in entry.lines.all())
                reversal = reverse_journal_entry(entry, request.user)
                if entry.voucher_type in ('receipt', 'payment') and cancel_amount > 0:
                    if entry.voucher_type == 'receipt':
                        update_cashbook(branch, entry.entry_date, payment_amount=cancel_amount)
                    else:
                        update_cashbook(branch, entry.entry_date, receipt_amount=cancel_amount)
            messages.success(request, f'Voucher {entry.voucher_no} cancelled. Reversal: {reversal.voucher_no}')
        except ValueError as e:
            messages.error(request, str(e))

        return redirect('accounting:vouchers')

    lines = entry.lines.all()
    return render(
        request,
        'accounting/voucher_cancel.html',
        {
            'entry': entry,
            'lines': lines,
        },
    )


@cashier_required
def account_search(request):
    """AJAX endpoint: search customer accounts by GL head type and query string."""
    q = request.GET.get('q', '').strip()
    head_id = request.GET.get('head_id', '')

    if not q or len(q) < 2:
        return JsonResponse({'results': []})

    try:
        head = ChartOfAccounts.objects.get(id=int(head_id))
    except (ChartOfAccounts.DoesNotExist, ValueError, TypeError):
        return JsonResponse({'results': []})

    results = []
    rt = head.related_table_name

    if rt in ('saving', 'current', 'security'):
        from apps.savings.models import SavingsAccount

        qs = (
            SavingsAccount.objects.filter(status='active')
            .filter(models.Q(account_no__icontains=q) | models.Q(member__name__icontains=q))
            .select_related('member')[:10]
        )
        results = [{'number': a.account_no, 'name': a.member.name, 'balance': str(a.current_balance)} for a in qs]

    elif rt in ('loan', 'advance'):
        from apps.loans.models import LoanAccount

        qs = (
            LoanAccount.objects.filter(status='disbursed')
            .filter(models.Q(loan_no__icontains=q) | models.Q(member__name__icontains=q))
            .select_related('member')[:10]
        )
        results = [{'number': a.loan_no, 'name': a.member.name, 'balance': str(a.outstanding_principal)} for a in qs]

    elif rt in ('agent', 'client'):
        from apps.agents.models import PigmmyAccount

        qs = (
            PigmmyAccount.objects.filter(status='active')
            .filter(models.Q(account_no__icontains=q) | models.Q(member__name__icontains=q))
            .select_related('member')[:10]
        )
        results = [{'number': a.account_no, 'name': a.member.name, 'balance': str(a.current_balance)} for a in qs]

    elif rt == 'fixed':
        from apps.deposits.models import FixedDeposit

        qs = (
            FixedDeposit.objects.filter(status='active')
            .filter(models.Q(fd_no__icontains=q) | models.Q(member__name__icontains=q))
            .select_related('member')[:10]
        )
        results = [{'number': a.fd_no, 'name': a.member.name, 'balance': str(a.deposit_amount)} for a in qs]

    elif rt == 'recurring':
        from apps.deposits.models import RecurringDeposit

        qs = (
            RecurringDeposit.objects.filter(status='active')
            .filter(models.Q(rd_no__icontains=q) | models.Q(member__name__icontains=q))
            .select_related('member')[:10]
        )
        results = [{'number': a.rd_no, 'name': a.member.name, 'balance': str(a.monthly_installment)} for a in qs]

    return JsonResponse({'results': results})


@manager_required
def inter_branch_transfer(request):
    from apps.branches.models import Branch

    from .models import InterBranchTransfer

    branches = Branch.objects.filter(status='active').order_by('branch_name')
    transfers = InterBranchTransfer.objects.select_related(
        'from_branch',
        'to_branch',
        'created_by',
    ).order_by('-transfer_date', '-created_at')[:50]

    if request.method == 'POST':
        from_branch_id = request.POST.get('from_branch')
        to_branch_id = request.POST.get('to_branch')
        amount_str = request.POST.get('amount', '0')
        narration = request.POST.get('narration', '')
        transfer_date_str = request.POST.get('transfer_date', '')

        try:
            from_branch = Branch.objects.get(pk=from_branch_id)
            to_branch = Branch.objects.get(pk=to_branch_id)
            amount = Decimal(amount_str)
            transfer_date = (
                date.fromisoformat(transfer_date_str)
                if transfer_date_str
                else get_transaction_date(request.current_branch)
            )
        except (Branch.DoesNotExist, Exception) as e:
            messages.error(request, f'Invalid input: {e}')
            return redirect('accounting:inter_branch_transfer')

        if from_branch == to_branch:
            messages.error(request, 'From and To branch cannot be the same.')
            return redirect('accounting:inter_branch_transfer')

        if amount <= 0:
            messages.error(request, 'Amount must be greater than zero.')
            return redirect('accounting:inter_branch_transfer')

        from .services import create_inter_branch_transfer

        try:
            transfer = create_inter_branch_transfer(
                from_branch=from_branch,
                to_branch=to_branch,
                amount=amount,
                transfer_date=transfer_date,
                narration=narration,
                user=request.user,
            )
            messages.success(
                request,
                f'Transfer {transfer.transfer_no}: ₹{amount:,.2f} from '
                f'{from_branch.branch_name} to {to_branch.branch_name}',
            )
        except Exception as e:
            messages.error(request, f'Transfer failed: {e}')

        return redirect('accounting:inter_branch_transfer')

    return render(
        request,
        'accounting/inter_branch_transfer.html',
        {
            'branches': branches,
            'transfers': transfers,
            'today': date.today(),
        },
    )
