from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ChartOfAccountsForm, VoucherForm
from .models import ChartOfAccounts, JournalEntry, JournalLine


@login_required
def voucher_list(request):
    entries = JournalEntry.objects.select_related('branch', 'created_by')
    if not request.user.can_access_all_branches:
        entries = entries.filter(branch=request.current_branch)
    entries = entries.order_by('-entry_date', '-created_at')[:50]
    return render(request, 'accounting/vouchers.html', {'entries': entries})


@login_required
def receipt_transaction(request):
    heads = ChartOfAccounts.objects.filter(allow_transactions=True, is_active=True).order_by('name')
    if request.method == 'POST':
        return _process_transaction(request, 'receipt', heads)
    return render(request, 'accounting/transaction.html', {
        'heads': heads,
        'txn_type': 'receipt',
        'title': 'Receipt Transaction',
    })


@login_required
def payment_transaction(request):
    heads = ChartOfAccounts.objects.filter(allow_transactions=True, is_active=True).order_by('name')
    if request.method == 'POST':
        return _process_transaction(request, 'payment', heads)
    return render(request, 'accounting/transaction.html', {
        'heads': heads,
        'txn_type': 'payment',
        'title': 'Payment Transaction',
    })


def _process_transaction(request, txn_type, heads):
    from apps.accounting.services import create_journal_entry

    entry_date_str = request.POST.get('entry_date', '')
    narration = request.POST.get('narration', '')
    total_forms = int(request.POST.get('lines-TOTAL_FORMS', 0))

    try:
        entry_date = date.fromisoformat(entry_date_str)
    except (ValueError, TypeError):
        entry_date = date.today()

    lines = []
    total_amount = Decimal('0')
    for i in range(total_forms):
        gl_id = request.POST.get(f'lines-{i}-gl_account')
        amount_str = request.POST.get(f'lines-{i}-amount', '0')
        desc = request.POST.get(f'lines-{i}-description', '')
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
        total_amount += amount

    if not lines:
        messages.error(request, 'No valid line items.')
        title = 'Receipt Transaction' if txn_type == 'receipt' else 'Payment Transaction'
        return render(request, 'accounting/transaction.html', {
            'heads': heads, 'txn_type': txn_type, 'title': title,
        })

    cash_head = ChartOfAccounts.objects.filter(
        related_table_name='general', name__icontains='cash',
    ).first()
    if not cash_head:
        cash_head = ChartOfAccounts.objects.filter(code__startswith='1').first()
    if not cash_head:
        messages.error(request, 'Cash account head not found. Create it in Chart of Accounts first.')
        title = 'Receipt Transaction' if txn_type == 'receipt' else 'Payment Transaction'
        return render(request, 'accounting/transaction.html', {
            'heads': heads, 'txn_type': txn_type, 'title': title,
        })

    if txn_type == 'receipt':
        lines.append({'account_code': cash_head.code, 'debit': total_amount, 'credit': Decimal('0')})
    else:
        lines.append({'account_code': cash_head.code, 'debit': Decimal('0'), 'credit': total_amount})

    try:
        branch = request.current_branch
        entry = create_journal_entry(
            entry_date=entry_date,
            voucher_type=txn_type,
            branch=branch,
            narration=narration,
            lines=lines,
            user=request.user,
        )
        messages.success(request, f'{txn_type.title()} {entry.voucher_no} saved.')
        return redirect('accounting:cashbook')
    except ValueError as e:
        messages.error(request, str(e))
        title = 'Receipt Transaction' if txn_type == 'receipt' else 'Payment Transaction'
        return render(request, 'accounting/transaction.html', {
            'heads': heads, 'txn_type': txn_type, 'title': title,
        })


@login_required
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

    today_entries = JournalEntry.objects.filter(
        entry_date=cb_date,
        voucher_type__in=['receipt', 'payment'],
    ).prefetch_related('lines')
    if not request.user.can_access_all_branches:
        today_entries = today_entries.filter(branch=request.current_branch)
    today_entries = today_entries.order_by('-created_at')

    from django.db.models import Sum

    receipt_total = today_entries.filter(voucher_type='receipt').aggregate(
        total=Sum('lines__credit_amount'),
    )['total'] or Decimal('0')
    payment_total = today_entries.filter(voucher_type='payment').aggregate(
        total=Sum('lines__debit_amount'),
    )['total'] or Decimal('0')

    return render(request, 'accounting/cashbook.html', {
        'heads': heads,
        'today_entries': today_entries,
        'total_receipts': receipt_total,
        'total_payments': payment_total,
        'cash_in_hand': receipt_total - payment_total,
        'cb_date': cb_date,
    })


@login_required
def voucher_create(request):
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


@login_required
def chart_of_accounts_list(request):
    heads = ChartOfAccounts.objects.filter(is_active=True).order_by('display_order', 'code')
    groups = {}
    for head in heads:
        group = head.get_account_group_display()
        groups.setdefault(group, []).append(head)
    return render(request, 'accounting/heads_list.html', {'groups': groups, 'total': heads.count()})


@login_required
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


@login_required
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


@login_required
def general_ledger(request):
    account_code = request.GET.get('account')
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    heads = ChartOfAccounts.objects.filter(
        allow_transactions=True, is_active=True,
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


@login_required
def day_book(request):
    book_date = request.GET.get('date')
    if book_date:
        try:
            book_date = date.fromisoformat(book_date)
        except ValueError:
            book_date = date.today()
    else:
        book_date = date.today()

    entries = JournalEntry.objects.filter(
        entry_date=book_date,
        is_reversed=False,
    ).prefetch_related('lines__gl_account').select_related('branch', 'created_by')
    if not request.user.can_access_all_branches:
        entries = entries.filter(branch=request.current_branch)
    entries = entries.order_by('voucher_type', 'created_at')

    return render(request, 'accounting/day_book.html', {
        'book_date': book_date,
        'entries': entries,
    })
