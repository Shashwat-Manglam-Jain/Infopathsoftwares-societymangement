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


def get_trial_balance(as_of_date=None, branch=None):
    qs = ChartOfAccounts.objects.filter(is_active=True, allow_transactions=True)
    if branch:
        qs = qs.filter(models.Q(branch=branch) | models.Q(branch__isnull=True))

    result = []
    total_debit = Decimal('0')
    total_credit = Decimal('0')

    for account in qs:
        lines_qs = JournalLine.objects.filter(
            gl_account=account,
            journal_entry__is_reversed=False,
        )
        if as_of_date:
            lines_qs = lines_qs.filter(journal_entry__entry_date__lte=as_of_date)
        if branch:
            lines_qs = lines_qs.filter(journal_entry__branch=branch)

        from django.db.models import Sum

        totals = lines_qs.aggregate(
            total_debit=Sum('debit_amount'),
            total_credit=Sum('credit_amount'),
        )
        dr = totals['total_debit'] or Decimal('0')
        cr = totals['total_credit'] or Decimal('0')

        if dr == 0 and cr == 0:
            continue

        balance = dr - cr
        entry = {
            'code': account.code,
            'name': account.name,
            'group': account.account_group,
            'debit': balance if balance > 0 else Decimal('0'),
            'credit': abs(balance) if balance < 0 else Decimal('0'),
        }
        total_debit += entry['debit']
        total_credit += entry['credit']
        result.append(entry)

    return {
        'accounts': result,
        'total_debit': total_debit,
        'total_credit': total_credit,
        'is_balanced': total_debit == total_credit,
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
        .annotate(seq_num=Cast(
            models.Func(
                models.F('voucher_no'),
                models.Value(f'{prefix}/'),
                models.Value(''),
                function='REPLACE',
            ),
            output_field=models.IntegerField(),
        ))
        .aggregate(max_val=Max('seq_num'))
    )['max_val']

    seq = (max_seq or 0) + 1
    return f'{prefix}/{seq:06d}'
