import calendar
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction

from apps.core.date_utils import get_transaction_date
from apps.savings.models import AccountTransaction


def deposit(
    account, amount, branch, user, payment_mode='cash', narration='', cheque_no=None, cheque_date=None, bank_name=None
):
    amount = Decimal(str(amount))
    if account.status != 'active':
        raise ValueError('Account is not active')
    if amount <= 0:
        raise ValueError('Amount must be positive')

    with transaction.atomic():
        account.current_balance += amount
        account.save(update_fields=['current_balance', 'updated_at'])

        txn_date = get_transaction_date(branch)
        receipt_no = _generate_receipt_no(branch, 'deposit')
        txn = AccountTransaction.objects.create(
            account=account,
            branch=branch,
            txn_date=txn_date,
            value_date=txn_date,
            txn_type='deposit',
            amount=amount,
            running_balance=account.current_balance,
            narration=narration or 'Cash deposit',
            receipt_no=receipt_no,
            payment_mode=payment_mode,
            cheque_no=cheque_no or '',
            cheque_date=cheque_date,
            bank_name=bank_name or '',
            created_by=user,
        )

        _create_deposit_journal(account, amount, branch, user, txn)
        return txn


def withdraw(account, amount, branch, user, payment_mode='cash', narration=''):
    amount = Decimal(str(amount))
    if account.status != 'active':
        raise ValueError('Account is not active')
    if amount <= 0:
        raise ValueError('Amount must be positive')
    if account.current_balance - amount < account.minimum_balance:
        raise ValueError(f'Insufficient balance. Minimum balance: {account.minimum_balance}')

    with transaction.atomic():
        account.current_balance -= amount
        account.save(update_fields=['current_balance', 'updated_at'])

        txn_date = get_transaction_date(branch)
        receipt_no = _generate_receipt_no(branch, 'withdrawal')
        txn = AccountTransaction.objects.create(
            account=account,
            branch=branch,
            txn_date=txn_date,
            value_date=txn_date,
            txn_type='withdrawal',
            amount=amount,
            running_balance=account.current_balance,
            narration=narration or 'Cash withdrawal',
            receipt_no=receipt_no,
            payment_mode=payment_mode,
            created_by=user,
        )

        _create_withdrawal_journal(account, amount, branch, user, txn)
        return txn


def calculate_daily_interest(account, for_date):
    if account.current_balance <= 0 or account.interest_rate <= 0:
        return Decimal('0.00')

    year = for_date.year
    days_in_year = Decimal(str(366 if calendar.isleap(year) else 365))
    daily_rate = account.interest_rate / (Decimal('100') * days_in_year)
    interest = (account.current_balance * daily_rate).quantize(
        Decimal('0.01'),
        rounding=ROUND_HALF_UP,
    )
    return interest


def post_interest(account, from_date, to_date, user):
    if account.status != 'active':
        raise ValueError('Account is not active')

    total_interest = Decimal('0.00')
    current_date = from_date
    while current_date <= to_date:
        total_interest += calculate_daily_interest(account, current_date)
        current_date += timedelta(days=1)

    total_interest = total_interest.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    if total_interest <= 0:
        return None

    with transaction.atomic():
        account.current_balance += total_interest
        account.last_interest_posted_date = to_date
        account.save(update_fields=['current_balance', 'last_interest_posted_date', 'updated_at'])

        txn = AccountTransaction.objects.create(
            account=account,
            branch=account.branch,
            txn_date=to_date,
            value_date=to_date,
            txn_type='interest_credit',
            amount=total_interest,
            running_balance=account.current_balance,
            narration=f'Interest credit {from_date} to {to_date}',
            payment_mode='transfer',
            created_by=user,
        )

        _create_interest_journal(account, total_interest, account.branch, user, txn)
        return txn


def reverse_transaction(txn, user):
    if txn.is_reversed:
        raise ValueError('Transaction is already reversed')

    with transaction.atomic():
        if txn.txn_type == 'deposit':
            txn.account.current_balance -= txn.amount
        elif txn.txn_type == 'withdrawal':
            txn.account.current_balance += txn.amount
        elif txn.txn_type == 'interest_credit':
            txn.account.current_balance -= txn.amount
        txn.account.save(update_fields=['current_balance', 'updated_at'])

        txn.is_reversed = True
        txn.save(update_fields=['is_reversed', 'updated_at'])

        reversal = AccountTransaction.objects.create(
            account=txn.account,
            branch=txn.branch,
            txn_date=date.today(),
            value_date=date.today(),
            txn_type='reversal',
            amount=txn.amount,
            running_balance=txn.account.current_balance,
            narration=f'Reversal of {txn.txn_type} {txn.voucher_no}',
            payment_mode=txn.payment_mode,
            created_by=user,
            is_reversed=True,
            reversal_of=txn,
        )

        from apps.accounting.models import JournalEntry
        from apps.accounting.services import reverse_journal_entry

        original_journal = JournalEntry.objects.filter(
            reference_type='savings_txn',
            reference_id=txn.pk,
            is_reversed=False,
        ).first()
        if not original_journal and txn.txn_type == 'interest_credit':
            original_journal = JournalEntry.objects.filter(
                reference_type='interest_posting',
                reference_id=txn.pk,
                is_reversed=False,
            ).first()
        if original_journal:
            reverse_journal_entry(original_journal, user)

        return reversal


def _create_deposit_journal(account, amount, branch, user, txn):
    from apps.accounting.services import create_journal_entry
    from apps.core.gl_utils import get_account_gl_code

    savings_code = get_account_gl_code(account, 'saving', '2001')
    create_journal_entry(
        entry_date=txn.txn_date,
        voucher_type='receipt',
        branch=branch,
        narration=f'Deposit to {account.account_no}',
        lines=[
            {'account_code': _get_cash_code(branch), 'debit': amount, 'credit': Decimal('0')},
            {'account_code': savings_code, 'debit': Decimal('0'), 'credit': amount},
        ],
        user=user,
        reference_type='savings_txn',
        reference_id=txn.pk,
    )


def _create_withdrawal_journal(account, amount, branch, user, txn):
    from apps.accounting.services import create_journal_entry
    from apps.core.gl_utils import get_account_gl_code

    savings_code = get_account_gl_code(account, 'saving', '2001')
    create_journal_entry(
        entry_date=txn.txn_date,
        voucher_type='payment',
        branch=branch,
        narration=f'Withdrawal from {account.account_no}',
        lines=[
            {'account_code': savings_code, 'debit': amount, 'credit': Decimal('0')},
            {'account_code': _get_cash_code(branch), 'debit': Decimal('0'), 'credit': amount},
        ],
        user=user,
        reference_type='savings_txn',
        reference_id=txn.pk,
    )


def _create_interest_journal(account, amount, branch, user, txn):
    from apps.accounting.services import create_journal_entry
    from apps.core.gl_utils import get_account_gl_code, get_gl_code, get_interest_head_code

    savings_code = get_account_gl_code(account, 'saving', '2001')
    gl_head = account.gl_head if hasattr(account, 'gl_head') and account.gl_head_id else None
    interest_expense_code = get_interest_head_code(gl_head, get_gl_code('interest_paid', '4001'))
    create_journal_entry(
        entry_date=txn.txn_date,
        voucher_type='journal',
        branch=branch,
        narration=f'Interest on savings {account.account_no}',
        lines=[
            {'account_code': interest_expense_code, 'debit': amount, 'credit': Decimal('0')},
            {'account_code': savings_code, 'debit': Decimal('0'), 'credit': amount},
        ],
        user=user,
        reference_type='interest_posting',
        reference_id=txn.pk,
    )


def _generate_receipt_no(branch, txn_type):
    prefix = 'RCT' if txn_type == 'deposit' else 'PMT'
    last = (
        AccountTransaction.objects.filter(
            branch=branch,
            receipt_no__startswith=prefix,
        )
        .order_by('-id')
        .first()
    )
    if last and last.receipt_no:
        try:
            seq = int(last.receipt_no.split('-')[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    return f'{prefix}-{branch.branch_code}-{seq:06d}'


def _get_cash_code(branch):
    from apps.accounting.models import ChartOfAccounts

    cash = ChartOfAccounts.objects.filter(
        account_type='cash',
        branch=branch,
    ).first()
    if cash:
        return cash.code
    return '1001'
