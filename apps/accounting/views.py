from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db import models, transaction
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.permissions import (
    accountant_required,
    admin_required,
    auditor_or_above,
    cashier_required,
    day_open_required,
    manager_required,
)

from .forms import ChartOfAccountsForm, InterestMasterForm, VoucherForm
from .models import ChartOfAccounts, InterestMaster, JournalEntry

CUSTOMER_ACCOUNT_TYPES = ('saving', 'current', 'recurring', 'fixed', 'security', 'loan', 'advance', 'agent')


@auditor_or_above
def voucher_list(request):
    entries = JournalEntry.objects.select_related('branch', 'created_by')
    if not request.user.can_access_all_branches:
        entries = entries.filter(branch=request.current_branch)
    entries = entries.order_by('-entry_date', '-created_at')[:50]
    return render(request, 'accounting/vouchers.html', {'entries': entries})


@cashier_required
@day_open_required
def receipt_transaction(request):
    if request.current_branch is None:
        messages.warning(request, 'Please select a specific branch before creating transactions.')
        return redirect('accounting:voucher_list')
    heads = ChartOfAccounts.objects.filter(allow_transactions=True, is_active=True).order_by('name')
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
        return redirect('accounting:voucher_list')
    heads = ChartOfAccounts.objects.filter(allow_transactions=True, is_active=True).order_by('name')
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

    entry_date_str = request.POST.get('entry_date', '')
    narration = request.POST.get('narration', '')
    raw_mode = request.POST.get('payment_mode', 'cash')
    payment_mode = 'cash' if raw_mode == 'cash' else 'transfer'
    total_forms = int(request.POST.get('lines-TOTAL_FORMS', 0))

    try:
        entry_date = date.fromisoformat(entry_date_str)
    except (ValueError, TypeError):
        entry_date = date.today()

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

    cash_head = ChartOfAccounts.objects.filter(
        related_table_name='general',
        name__icontains='cash',
    ).first()
    if not cash_head:
        cash_head = ChartOfAccounts.objects.filter(code__startswith='1').first()
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
    prev_cb = CashbookMaster.objects.filter(
        txn_date__lt=cb_date, **branch_filter,
    ).order_by('-txn_date').first()
    opening_cash = prev_cb.closing_balance if prev_cb else Decimal('0')
    closing_cash = opening_cash + receipt_cash - payment_cash

    return render(
        request,
        'accounting/cashbook.html',
        {
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
        },
    )


@accountant_required
@day_open_required
def voucher_create(request):
    if request.current_branch is None:
        messages.warning(request, 'Please select a specific branch before creating vouchers.')
        return redirect('accounting:voucher_list')
    if request.method == 'POST':
        form = VoucherForm(request.POST)
        if form.is_valid():
            from apps.accounting.services import create_journal_entry

            amount = form.cleaned_data['amount']
            try:
                branch = request.current_branch
                entry = create_journal_entry(
                    entry_date=date.today(),
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
    groups = {}
    for head in heads:
        group = head.get_account_group_display()
        groups.setdefault(group, []).append(head)
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
    return render(request, 'accounting/interest_master_list.html', {'slabs': slabs})


@admin_required
def interest_master_create(request):
    if request.method == 'POST':
        form = InterestMasterForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Interest slab created.')
            return redirect('accounting:interest_master')
    else:
        form = InterestMasterForm()
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
    return render(request, 'accounting/cashbook_report.html', context)


@admin_required
def opening_balance_update(request):
    heads = ChartOfAccounts.objects.filter(
        allow_transactions=True,
        is_active=True,
    ).order_by('display_order', 'code')

    if request.method == 'POST':
        head_id = request.POST.get('head_id')
        new_balance = request.POST.get('opening_balance', '0')
        try:
            head = ChartOfAccounts.objects.get(pk=head_id)
            head.opening_balance = Decimal(new_balance)
            head.save(update_fields=['opening_balance'])
            messages.success(request, f'Opening balance updated for {head.name}: {new_balance}')
        except (ChartOfAccounts.DoesNotExist, InvalidOperation):
            messages.error(request, 'Invalid head or amount.')
        return redirect('accounting:opening_balance')

    return render(request, 'accounting/opening_balance.html', {'heads': heads})


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
def voucher_edit(request, pk):
    if request.current_branch is None:
        messages.warning(request, 'Please select a specific branch before editing vouchers.')
        return redirect('accounting:voucher_list')
    entry = get_object_or_404(
        JournalEntry.objects.prefetch_related('lines__gl_account'),
        pk=pk,
    )
    if entry.is_reversed:
        messages.error(request, 'Cannot edit a reversed voucher.')
        return redirect('accounting:vouchers')
    if entry.entry_date != date.today():
        messages.error(request, 'Can only edit vouchers created today.')
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
            from apps.accounting.services import create_journal_entry, reverse_journal_entry

            try:
                reverse_journal_entry(entry, request.user)
                new_amount = form.cleaned_data['amount']
                new_entry = create_journal_entry(
                    entry_date=date.today(),
                    voucher_type=form.cleaned_data['voucher_type'],
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
def voucher_cancel(request, pk):
    entry = get_object_or_404(
        JournalEntry.objects.prefetch_related('lines__gl_account'),
        pk=pk,
    )

    if request.method == 'POST':
        if entry.is_reversed:
            messages.error(request, 'This voucher is already reversed/cancelled.')
            return redirect('accounting:vouchers')

        from apps.accounting.services import reverse_journal_entry

        try:
            reversal = reverse_journal_entry(entry, request.user)
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

    elif rt == 'agent':
        from apps.agents.models import PigmmyAccount

        qs = (
            PigmmyAccount.objects.filter(status='active')
            .filter(models.Q(account_no__icontains=q) | models.Q(member__name__icontains=q))
            .select_related('member')[:10]
        )
        results = [{'number': a.account_no, 'name': a.member.name, 'balance': str(a.current_balance)} for a in qs]

    return JsonResponse({'results': results})
