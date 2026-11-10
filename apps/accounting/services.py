from decimal import Decimal

from django.db import models, transaction

from apps.accounting.models import ChartOfAccounts, JournalEntry, JournalLine


def create_journal_entry(
    entry_date, voucher_type, branch, narration, lines, user, reference_type='manual', reference_id=None
):
    total_debit = sum(Decimal(str(line.get('debit', 0))) for line in lines)
    total_credit = sum(Decimal(str(line.get('credit', 0))) for line in lines)
    if total_debit != total_credit:
        raise ValueError(f'Journal entry does not balance: Debit={total_debit}, Credit={total_credit}')

    for line_data in lines:
        code = line_data['account_code']
        if not ChartOfAccounts.objects.filter(code=code).exists():
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
            created_by=user,
        )

        for line_data in lines:
            account = ChartOfAccounts.objects.get(code=line_data['account_code'])
            debit = Decimal(str(line_data.get('debit', 0)))
            credit = Decimal(str(line_data.get('credit', 0)))

            JournalLine.objects.create(
                journal_entry=entry,
                gl_account=account,
                debit_amount=debit,
                credit_amount=credit,
                narration=line_data.get('narration', ''),
            )

            if account.account_group in ('asset', 'expense'):
                account.current_balance += debit - credit
            else:
                account.current_balance += credit - debit
            account.save(update_fields=['current_balance'])

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
        )
        reversal.reversal_of = entry
        reversal.save(update_fields=['reversal_of'])

        entry.is_reversed = True
        entry.save(update_fields=['is_reversed'])
        return reversal


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

    for account in qs:
        ob = account.opening_balance or Decimal('0')

        if from_date:
            pre_lines = JournalLine.objects.filter(
                gl_account=account,
                journal_entry__is_reversed=False,
                journal_entry__is_posted=True,
                journal_entry__entry_date__lt=from_date,
            )
            if branch:
                pre_lines = pre_lines.filter(journal_entry__branch=branch)
            pre = pre_lines.aggregate(dr=Sum('debit_amount'), cr=Sum('credit_amount'))
            pre_dr = pre['dr'] or Decimal('0')
            pre_cr = pre['cr'] or Decimal('0')
            if account.account_group in ('asset', 'expense'):
                ob += pre_dr - pre_cr
            else:
                ob += pre_cr - pre_dr

        period_qs = JournalLine.objects.filter(
            gl_account=account,
            journal_entry__is_reversed=False,
            journal_entry__is_posted=True,
        )
        if from_date:
            period_qs = period_qs.filter(journal_entry__entry_date__gte=from_date)
        if to_date:
            period_qs = period_qs.filter(journal_entry__entry_date__lte=to_date)
        if branch:
            period_qs = period_qs.filter(journal_entry__branch=branch)

        period = period_qs.aggregate(dr=Sum('debit_amount'), cr=Sum('credit_amount'))
        p_dr = period['dr'] or Decimal('0')
        p_cr = period['cr'] or Decimal('0')

        if account.account_group in ('asset', 'expense'):
            closing = ob + p_dr - p_cr
        else:
            closing = ob + p_cr - p_dr

        if ob == 0 and p_dr == 0 and p_cr == 0:
            continue

        entry = {
            'code': account.code,
            'name': account.name,
            'group': account.account_group,
            'opening_balance': ob,
            'opening_debit': ob if ob > 0 else Decimal('0'),
            'opening_credit': abs(ob) if ob < 0 else Decimal('0'),
            'period_debit': p_dr,
            'period_credit': p_cr,
            'closing_balance': closing,
            'closing_debit': closing if closing > 0 else Decimal('0'),
            'closing_credit': abs(closing) if closing < 0 else Decimal('0'),
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
    lines_qs = JournalLine.objects.filter(
        gl_account=account,
        journal_entry__entry_date__gte=from_date,
        journal_entry__entry_date__lte=to_date,
        journal_entry__is_posted=True,
    ).select_related('journal_entry', 'journal_entry__branch')

    if branch:
        lines_qs = lines_qs.filter(journal_entry__branch=branch)

    lines_qs = lines_qs.order_by('journal_entry__entry_date', 'journal_entry__created_at')

    from django.db.models import Sum

    opening_lines = JournalLine.objects.filter(
        gl_account=account,
        journal_entry__entry_date__lt=from_date,
        journal_entry__is_posted=True,
    )
    if branch:
        opening_lines = opening_lines.filter(journal_entry__branch=branch)
    opening = opening_lines.aggregate(
        dr=Sum('debit_amount'),
        cr=Sum('credit_amount'),
    )
    opening_balance = (opening['dr'] or Decimal('0')) - (opening['cr'] or Decimal('0'))

    entries = []
    running = opening_balance
    for line in lines_qs:
        running += line.debit_amount - line.credit_amount
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

    return {
        'account': account,
        'opening_balance': opening_balance,
        'entries': entries,
        'closing_balance': running,
    }


def generate_voucher_no(voucher_type, branch):
    prefix_map = {
        'receipt': 'R',
        'payment': 'P',
        'journal': 'J',
        'contra': 'C',
    }
    prefix = prefix_map.get(voucher_type, 'V')

    from django.db.models import Max
    from django.db.models.functions import Cast

    max_seq = (
        JournalEntry.objects.filter(
            voucher_type=voucher_type,
            branch=branch,
            voucher_no__startswith=f'{prefix}/',
        )
        .annotate(
            seq_num=Cast(
                models.Func(
                    models.F('voucher_no'),
                    models.Value(f'{prefix}/'),
                    models.Value(''),
                    function='REPLACE',
                ),
                output_field=models.IntegerField(),
            )
        )
        .aggregate(max_val=Max('seq_num'))
    )['max_val']

    seq = (max_seq or 0) + 1
    return f'{prefix}/{seq:06d}'
