from decimal import Decimal

from django.db import models, transaction
from django.utils import timezone

from apps.accounting.models import CashbookMaster, ChartOfAccounts, JournalEntry, JournalLine


def create_journal_entry(
    entry_date,
    voucher_type,
    branch,
    narration,
    lines,
    user,
    reference_type='manual',
    reference_id=None,
    payment_mode='cash',
    is_posted=False,
):
    total_debit = sum(Decimal(str(line.get('debit', 0))) for line in lines)
    total_credit = sum(Decimal(str(line.get('credit', 0))) for line in lines)
    if total_debit != total_credit:
        raise ValueError(f'Journal entry does not balance: Debit={total_debit}, Credit={total_credit}')

    codes = [line_data['account_code'] for line_data in lines]
    accounts_by_code = {a.code: a for a in ChartOfAccounts.objects.filter(code__in=codes)}
    for code in codes:
        if code not in accounts_by_code:
            raise ValueError(
                f'GL head with code "{code}" does not exist. Create it in Head Master (Chart of Accounts) first.'
            )

    with transaction.atomic():
        voucher_no = generate_voucher_no(voucher_type, branch)
        entry = JournalEntry.objects.create(
            entry_date=entry_date,
            voucher_no=voucher_no,
            voucher_type=voucher_type,
            branch=branch,
            narration=narration,
            reference_type=reference_type,
            reference_id=reference_id,
            payment_mode=payment_mode,
            created_by=user,
            is_posted=is_posted,
            approved_by=user if is_posted else None,
            posted_at=timezone.now() if is_posted else None,
        )

        if is_posted:
            accounts_map = {a.code: a for a in ChartOfAccounts.objects.select_for_update().filter(code__in=codes)}
        else:
            accounts_map = accounts_by_code

        for line_data in lines:
            account = accounts_map[line_data['account_code']]
            debit = Decimal(str(line_data.get('debit', 0)))
            credit = Decimal(str(line_data.get('credit', 0)))

            JournalLine.objects.create(
                journal_entry=entry,
                gl_account=account,
                debit_amount=debit,
                credit_amount=credit,
                narration=line_data.get('narration', ''),
                account_number=line_data.get('account_number', ''),
            )

            if is_posted:
                account.debit_balance += debit
                account.credit_balance += credit
                if account.account_group in ('asset', 'expense'):
                    account.current_balance += debit - credit
                else:
                    account.current_balance += credit - debit
                account.save(update_fields=['current_balance', 'debit_balance', 'credit_balance'])

        from apps.audit.middleware import get_current_ip
        from apps.audit.services import log_action

        log_action(
            user=user,
            branch=branch,
            action='create',
            table_name='JournalEntry',
            record_id=entry.pk,
            new_values={
                'voucher_no': entry.voucher_no,
                'voucher_type': voucher_type,
                'narration': narration,
                'reference_type': reference_type,
                'total': str(total_debit),
                'is_posted': is_posted,
            },
            ip_address=get_current_ip(),
        )
        return entry


def reverse_journal_entry(entry, user):
    if entry.is_reversed:
        raise ValueError('Entry is already reversed')

    with transaction.atomic():
        reversed_lines = []
        for line in entry.lines.all():
            reversed_lines.append(
                {
                    'account_code': line.gl_account.code,
                    'debit': line.credit_amount,
                    'credit': line.debit_amount,
                    'narration': f'Reversal: {line.narration}',
                }
            )

        reversal = create_journal_entry(
            entry_date=entry.entry_date,
            voucher_type=entry.voucher_type,
            branch=entry.branch,
            narration=f'Reversal of {entry.voucher_no}: {entry.narration}',
            lines=reversed_lines,
            user=user,
            reference_type=entry.reference_type,
            reference_id=entry.reference_id,
            payment_mode=entry.payment_mode,
            is_posted=True,
        )
        reversal.reversal_of = entry
        reversal.is_reversed = True
        reversal.save(update_fields=['reversal_of', 'is_reversed'])

        entry.is_reversed = True
        entry.save(update_fields=['is_reversed'])

        from apps.audit.middleware import get_current_ip
        from apps.audit.services import log_action

        log_action(
            user=user,
            branch=entry.branch,
            action='reverse',
            table_name='JournalEntry',
            record_id=entry.pk,
            old_values={'voucher_no': entry.voucher_no, 'is_reversed': False},
            new_values={'reversal_voucher': reversal.voucher_no, 'is_reversed': True},
            ip_address=get_current_ip(),
        )
        return reversal


def post_journal_entry(entry, user):
    if entry.is_posted:
        raise ValueError('Entry is already posted.')
    if entry.is_reversed:
        raise ValueError('Cannot post a reversed entry.')
    if entry.is_rejected:
        raise ValueError('Cannot post a rejected entry.')

    with transaction.atomic():
        codes = list(entry.lines.values_list('gl_account__code', flat=True))
        locked_accounts = {a.code: a for a in ChartOfAccounts.objects.select_for_update().filter(code__in=codes)}
        for line in entry.lines.select_related('gl_account'):
            account = locked_accounts[line.gl_account.code]
            account.debit_balance += line.debit_amount
            account.credit_balance += line.credit_amount
            if account.account_group in ('asset', 'expense'):
                account.current_balance += line.debit_amount - line.credit_amount
            else:
                account.current_balance += line.credit_amount - line.debit_amount
            account.save(update_fields=['current_balance', 'debit_balance', 'credit_balance'])

        entry.is_posted = True
        entry.approved_by = user
        entry.posted_at = timezone.now()
        entry.save(update_fields=['is_posted', 'approved_by', 'posted_at'])

        from apps.audit.middleware import get_current_ip
        from apps.audit.services import log_action

        log_action(
            user=user,
            branch=entry.branch,
            action='post',
            table_name='JournalEntry',
            record_id=entry.pk,
            old_values={'is_posted': False},
            new_values={'is_posted': True, 'approved_by': user.pk},
            ip_address=get_current_ip(),
        )
    return entry


def reject_journal_entry(entry, user):
    if entry.is_posted:
        raise ValueError('Cannot reject a posted entry.')
    if entry.is_rejected:
        raise ValueError('Entry is already rejected.')
    if entry.is_system_entry:
        raise ValueError('System-generated entries cannot be rejected.')

    with transaction.atomic():
        entry.is_rejected = True
        entry.rejected_by = user
        entry.rejected_at = timezone.now()
        entry.save(update_fields=['is_rejected', 'rejected_by', 'rejected_at'])

        from apps.audit.middleware import get_current_ip
        from apps.audit.services import log_action

        log_action(
            user=user,
            branch=entry.branch,
            action='reject',
            table_name='JournalEntry',
            record_id=entry.pk,
            old_values={'is_rejected': False},
            new_values={'is_rejected': True, 'rejected_by': user.pk},
            ip_address=get_current_ip(),
        )
    return entry


def batch_post_entries(queryset, user):
    posted_count = 0
    for entry in queryset.filter(is_posted=False, is_reversed=False, is_rejected=False):
        post_journal_entry(entry, user)
        posted_count += 1
    return posted_count


def update_cashbook(branch, txn_date, receipt_amount=Decimal('0'), payment_amount=Decimal('0'), payment_mode='cash'):
    from django.db.models import F

    from apps.core.gl_utils import get_cash_code

    cb, created = CashbookMaster.objects.get_or_create(
        branch=branch,
        txn_date=txn_date,
        defaults={'opening_balance': Decimal('0')},
    )
    if created:
        prev = (
            CashbookMaster.objects.filter(
                branch=branch,
                txn_date__lt=txn_date,
            )
            .order_by('-txn_date')
            .first()
        )
        if prev:
            cb.opening_balance = prev.closing_balance
        else:
            cash_code = get_cash_code(branch)
            cash_head = ChartOfAccounts.objects.filter(code=cash_code).first()
            cb.opening_balance = cash_head.opening_balance if cash_head else Decimal('0')
        cb.save(update_fields=['opening_balance'])

    update_fields = {
        'total_receipts': F('total_receipts') + receipt_amount,
        'total_payments': F('total_payments') + payment_amount,
    }
    if payment_mode == 'cash':
        update_fields['receipt_cash'] = F('receipt_cash') + receipt_amount
        update_fields['payment_cash'] = F('payment_cash') + payment_amount
    else:
        update_fields['receipt_transfer'] = F('receipt_transfer') + receipt_amount
        update_fields['payment_transfer'] = F('payment_transfer') + payment_amount

    CashbookMaster.objects.filter(pk=cb.pk).update(**update_fields)
    CashbookMaster.objects.filter(pk=cb.pk).update(
        closing_balance=F('opening_balance') + F('total_receipts') - F('total_payments'),
    )
    cb.refresh_from_db()
    return cb


def get_trial_balance(from_date=None, to_date=None, branch=None, as_of_date=None):
    """Trial balance with opening balances and period-based Dr/Cr.

    If only as_of_date is given (legacy call), behaves as cumulative up to that date.
    If from_date and to_date are given, shows opening + period movement + closing.
    """
    from django.db.models import Sum

    if as_of_date and not to_date:
        to_date = as_of_date
    if to_date and not from_date:
        from_date = None

    qs = ChartOfAccounts.objects.filter(is_active=True, allow_transactions=True)
    if branch:
        qs = qs.filter(models.Q(branch=branch) | models.Q(branch__isnull=True))

    result = []
    totals = {
        'opening_debit': Decimal('0'),
        'opening_credit': Decimal('0'),
        'period_debit': Decimal('0'),
        'period_credit': Decimal('0'),
        'closing_debit': Decimal('0'),
        'closing_credit': Decimal('0'),
    }

    base_jl_filter = models.Q(
        journal_entry__is_reversed=False,
        journal_entry__is_posted=True,
        gl_account__in=qs,
    )
    if branch:
        base_jl_filter &= models.Q(journal_entry__branch=branch)

    pre_map = {}
    if from_date:
        pre_aggs = (
            JournalLine.objects.filter(base_jl_filter, journal_entry__entry_date__lt=from_date)
            .values('gl_account_id')
            .annotate(dr=Sum('debit_amount'), cr=Sum('credit_amount'))
        )
        pre_map = {row['gl_account_id']: row for row in pre_aggs}

    period_filter = base_jl_filter
    if from_date:
        period_filter &= models.Q(journal_entry__entry_date__gte=from_date)
    if to_date:
        period_filter &= models.Q(journal_entry__entry_date__lte=to_date)
    period_aggs = (
        JournalLine.objects.filter(period_filter)
        .values('gl_account_id')
        .annotate(dr=Sum('debit_amount'), cr=Sum('credit_amount'))
    )
    period_map = {row['gl_account_id']: row for row in period_aggs}

    for account in qs:
        ob = account.opening_balance or Decimal('0')

        if from_date:
            pre = pre_map.get(account.pk, {})
            pre_dr = pre.get('dr') or Decimal('0')
            pre_cr = pre.get('cr') or Decimal('0')
            if account.account_group in ('asset', 'expense'):
                ob += pre_dr - pre_cr
            else:
                ob += pre_cr - pre_dr

        prd = period_map.get(account.pk, {})
        p_dr = prd.get('dr') or Decimal('0')
        p_cr = prd.get('cr') or Decimal('0')

        if account.account_group in ('asset', 'expense'):
            closing = ob + p_dr - p_cr
        else:
            closing = ob + p_cr - p_dr

        if ob == 0 and p_dr == 0 and p_cr == 0:
            continue

        is_debit_normal = account.account_group in ('asset', 'expense')
        if is_debit_normal:
            ob_dr = ob if ob > 0 else Decimal('0')
            ob_cr = abs(ob) if ob < 0 else Decimal('0')
            cl_dr = closing if closing > 0 else Decimal('0')
            cl_cr = abs(closing) if closing < 0 else Decimal('0')
        else:
            ob_cr = ob if ob > 0 else Decimal('0')
            ob_dr = abs(ob) if ob < 0 else Decimal('0')
            cl_cr = closing if closing > 0 else Decimal('0')
            cl_dr = abs(closing) if closing < 0 else Decimal('0')

        entry = {
            'code': account.code,
            'name': account.name,
            'group': account.account_group,
            'opening_balance': ob,
            'opening_debit': ob_dr,
            'opening_credit': ob_cr,
            'period_debit': p_dr,
            'period_credit': p_cr,
            'closing_balance': closing,
            'closing_debit': cl_dr,
            'closing_credit': cl_cr,
            'debit': p_dr,
            'credit': p_cr,
        }
        for key in (
            'opening_debit',
            'opening_credit',
            'period_debit',
            'period_credit',
            'closing_debit',
            'closing_credit',
        ):
            totals[key] += entry[key]
        result.append(entry)

    return {
        'accounts': result,
        'total_debit': totals['closing_debit'],
        'total_credit': totals['closing_credit'],
        'totals': totals,
        'is_balanced': totals['closing_debit'] == totals['closing_credit'],
    }


def get_ledger(account_code, from_date, to_date, branch=None):
    account = ChartOfAccounts.objects.get(code=account_code)
    is_debit_normal = account.account_group in ('asset', 'expense')

    lines_qs = JournalLine.objects.filter(
        gl_account=account,
        journal_entry__entry_date__gte=from_date,
        journal_entry__entry_date__lte=to_date,
        journal_entry__is_posted=True,
        journal_entry__is_reversed=False,
    ).select_related('journal_entry', 'journal_entry__branch')

    if branch:
        lines_qs = lines_qs.filter(journal_entry__branch=branch)

    lines_qs = lines_qs.order_by('journal_entry__entry_date', 'journal_entry__created_at')

    from django.db.models import Sum

    opening_lines = JournalLine.objects.filter(
        gl_account=account,
        journal_entry__entry_date__lt=from_date,
        journal_entry__is_posted=True,
        journal_entry__is_reversed=False,
    )
    if branch:
        opening_lines = opening_lines.filter(journal_entry__branch=branch)
    opening = opening_lines.aggregate(
        dr=Sum('debit_amount'),
        cr=Sum('credit_amount'),
    )
    pre_dr = opening['dr'] or Decimal('0')
    pre_cr = opening['cr'] or Decimal('0')

    ob = account.opening_balance or Decimal('0')
    if is_debit_normal:
        opening_balance = ob + pre_dr - pre_cr
    else:
        opening_balance = ob + pre_cr - pre_dr

    entries = []
    running = opening_balance
    for line in lines_qs:
        if is_debit_normal:
            running += line.debit_amount - line.credit_amount
        else:
            running += line.credit_amount - line.debit_amount
        entries.append(
            {
                'date': line.journal_entry.entry_date,
                'voucher_no': line.journal_entry.voucher_no,
                'narration': line.journal_entry.narration,
                'debit': line.debit_amount,
                'credit': line.credit_amount,
                'balance': running,
            }
        )

    total_debit = sum(e['debit'] for e in entries)
    total_credit = sum(e['credit'] for e in entries)

    return {
        'account': account,
        'opening_balance': opening_balance,
        'entries': entries,
        'closing_balance': running,
        'total_debit': total_debit,
        'total_credit': total_credit,
    }


def generate_voucher_no(voucher_type, branch):
    prefix_map = {
        'receipt': 'R',
        'payment': 'P',
        'journal': 'J',
        'contra': 'C',
    }
    prefix = prefix_map.get(voucher_type, 'V')

    last = (
        JournalEntry.objects.select_for_update()
        .filter(
            voucher_type=voucher_type,
            branch=branch,
            voucher_no__startswith=f'{prefix}/',
        )
        .order_by('-id')
        .first()
    )

    if last and last.voucher_no:
        try:
            seq = int(last.voucher_no.split('/')[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    return f'{prefix}/{seq:06d}'
