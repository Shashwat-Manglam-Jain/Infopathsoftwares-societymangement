from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from .models import DayEndLog, MonthEndLog, WorkingDay, YearEndLog


@transaction.atomic
def begin_working_day(branch, working_date, user):
    """Set the transaction date for a branch. Must be called before any transaction."""
    wd, created = WorkingDay.objects.get_or_create(
        branch=branch,
        defaults={
            'current_date': working_date,
            'is_day_open': True,
            'opened_by': user,
            'opened_at': timezone.now(),
        },
    )
    if not created:
        if wd.is_day_open:
            raise ValueError(
                f'Day is already open for {branch.branch_name} on {wd.current_date}. '
                f'Run Day End before opening a new day.'
            )
        wd.last_working_date = wd.current_date
        wd.current_date = working_date
        wd.is_day_open = True
        wd.day_end_completed = False
        wd.cashbook_posted = False
        wd.opened_by = user
        wd.opened_at = timezone.now()
        wd.save()
    return wd


@transaction.atomic
def run_day_end(branch, user):
    """Execute day-end procedure for a branch.

    Steps:
    1. Accrue savings interest
    2. Accrue loan interest
    3. Mark overdue EMIs
    4. Mark NPA loans
    5. Auto-post cashbook (aggregate transactions → GL entries)
    6. Close the day
    """
    wd = WorkingDay.objects.select_for_update().get(branch=branch)
    if not wd.is_day_open:
        raise ValueError(f'No working day is open for {branch.branch_name}.')

    processing_date = wd.current_date

    existing = DayEndLog.objects.filter(branch=branch, processing_date=processing_date).first()
    if existing and existing.status == 'completed':
        raise ValueError(f'Day End already completed for {processing_date}.')

    if existing:
        existing.status = 'running'
        existing.error_log = ''
        existing.completed_at = None
        existing.run_by = user
        existing.save()
        log = existing
    else:
        log = DayEndLog.objects.create(
            branch=branch,
            processing_date=processing_date,
            status='running',
            run_by=user,
        )

    try:
        log.savings_interest_accrued_count = _accrue_savings_interest(branch, processing_date)
        log.loan_interest_accrued_count = _accrue_loan_interest(branch, processing_date)
        log.loans_marked_overdue_count = _mark_overdue_loans(branch, processing_date)
        log.loans_marked_npa_count = _mark_npa_loans(branch, processing_date)
        log.cashbook_entries_posted = _auto_cashbook_posting(branch, processing_date, user)

        log.status = 'completed'
        log.completed_at = timezone.now()
        log.save()

        wd.day_end_completed = True
        wd.cashbook_posted = True
        wd.is_day_open = False
        wd.save()

        return log
    except Exception as e:
        log.status = 'failed'
        log.error_log = str(e)
        log.completed_at = timezone.now()
        log.save()
        raise


def rollback_day_end(branch, processing_date, user):
    """Roll back day-end flag to allow more transactions (Day End Flag Correction)."""
    log = DayEndLog.objects.filter(branch=branch, processing_date=processing_date, status='completed').first()
    if not log:
        raise ValueError(f'No completed Day End found for {processing_date}.')

    log.status = 'rolled_back'
    log.save()

    wd = WorkingDay.objects.get(branch=branch)
    wd.current_date = processing_date
    wd.is_day_open = True
    wd.day_end_completed = False
    wd.cashbook_posted = False
    wd.save()

    return log


@transaction.atomic
def run_month_end(branch, month_date, user):
    """Monthly processing: calculate loan interest demand, RD installment dues.

    month_date: first day of the month being processed
    """
    from apps.loans.models import EMISchedule, LoanAccount

    if MonthEndLog.objects.filter(branch=branch, month=month_date, status='completed').exists():
        raise ValueError(f'Month End already completed for {month_date.strftime("%b %Y")}.')

    log = MonthEndLog.objects.create(
        branch=branch,
        month=month_date,
        status='running',
        run_by=user,
    )

    try:
        loan_count = 0
        demand_count = 0

        loans = LoanAccount.objects.filter(branch=branch, status__in=['disbursed', 'npa'])
        last_day = date(
            month_date.year + (1 if month_date.month == 12 else 0), (month_date.month % 12) + 1, 1
        ) - timedelta(days=1)

        for loan in loans:
            daily_rate = loan.interest_rate / Decimal('365') / Decimal('100')
            days_in_month = last_day.day
            monthly_interest = loan.outstanding_principal * daily_rate * days_in_month
            loan.outstanding_interest += monthly_interest
            loan.save(update_fields=['outstanding_interest'])
            loan_count += 1

            due_emis = EMISchedule.objects.filter(
                loan=loan,
                due_date__month=month_date.month,
                due_date__year=month_date.year,
                status='pending',
            )
            demand_count += due_emis.count()

        # Check RD installments due
        from apps.deposits.models import RDInstallment

        rd_count = RDInstallment.objects.filter(
            rd__branch=branch,
            rd__status='active',
            due_date__month=month_date.month,
            due_date__year=month_date.year,
            status='pending',
        ).count()

        log.loan_interest_calculated_count = loan_count
        log.demand_generated_count = demand_count
        log.rd_installments_due_count = rd_count
        log.status = 'completed'
        log.completed_at = timezone.now()
        log.save()

        return log
    except Exception as e:
        log.status = 'failed'
        log.error_log = str(e)
        log.completed_at = timezone.now()
        log.save()
        raise


@transaction.atomic
def run_year_end(branch, financial_year, user):
    """Year-end procedure: zero out P&L accounts, update opening balances.

    Steps:
    1. Calculate net profit/loss from income and expense accounts
    2. Transfer P&L to reserves (or opening balance)
    3. Zero out all income and expense account balances
    4. Set new financial year opening balances
    """
    from apps.accounting.models import ChartOfAccounts, JournalLine

    if YearEndLog.objects.filter(financial_year=financial_year, branch=branch, status='completed').exists():
        raise ValueError(f'Year End already completed for {financial_year.fy_code}.')

    log = YearEndLog.objects.create(
        financial_year=financial_year,
        branch=branch,
        status='running',
        run_by=user,
    )

    try:
        total_income = Decimal('0')
        total_expense = Decimal('0')
        pl_count = 0
        ob_count = 0

        income_accounts = ChartOfAccounts.objects.filter(account_group='income')
        expense_accounts = ChartOfAccounts.objects.filter(account_group='expense')

        for account in income_accounts:
            lines = JournalLine.objects.filter(
                gl_account=account,
                journal_entry__entry_date__gte=financial_year.start_date,
                journal_entry__entry_date__lte=financial_year.end_date,
            )
            agg = lines.aggregate(dr=Sum('debit_amount'), cr=Sum('credit_amount'))
            balance = (agg['cr'] or Decimal('0')) - (agg['dr'] or Decimal('0'))
            total_income += balance

        for account in expense_accounts:
            lines = JournalLine.objects.filter(
                gl_account=account,
                journal_entry__entry_date__gte=financial_year.start_date,
                journal_entry__entry_date__lte=financial_year.end_date,
            )
            agg = lines.aggregate(dr=Sum('debit_amount'), cr=Sum('credit_amount'))
            balance = (agg['dr'] or Decimal('0')) - (agg['cr'] or Decimal('0'))
            total_expense += balance

        profit_or_loss = total_income - total_expense

        # Transfer profit/loss to reserves BEFORE zeroing P&L accounts.
        # create_journal_entry updates current_balance on the accounts it
        # touches, so it must run while the P&L balances are still live.
        reserves_account = ChartOfAccounts.objects.filter(
            related_table_name='general',
            name__icontains='reserve',
            account_group='equity',
        ).first()
        if not reserves_account:
            reserves_account = ChartOfAccounts.objects.filter(
                account_group='equity',
                allow_transactions=True,
            ).first()

        if reserves_account and profit_or_loss != Decimal('0'):
            from apps.accounting.services import create_journal_entry

            closing_lines = []
            for account in income_accounts:
                bal = JournalLine.objects.filter(
                    gl_account=account,
                    journal_entry__entry_date__gte=financial_year.start_date,
                    journal_entry__entry_date__lte=financial_year.end_date,
                ).aggregate(dr=Sum('debit_amount'), cr=Sum('credit_amount'))
                net = (bal['cr'] or Decimal('0')) - (bal['dr'] or Decimal('0'))
                if net > 0:
                    closing_lines.append({'account_code': account.code, 'debit': net, 'credit': Decimal('0')})
            for account in expense_accounts:
                bal = JournalLine.objects.filter(
                    gl_account=account,
                    journal_entry__entry_date__gte=financial_year.start_date,
                    journal_entry__entry_date__lte=financial_year.end_date,
                ).aggregate(dr=Sum('debit_amount'), cr=Sum('credit_amount'))
                net = (bal['dr'] or Decimal('0')) - (bal['cr'] or Decimal('0'))
                if net > 0:
                    closing_lines.append({'account_code': account.code, 'debit': Decimal('0'), 'credit': net})

            if profit_or_loss > 0:
                closing_lines.append(
                    {'account_code': reserves_account.code, 'debit': Decimal('0'), 'credit': profit_or_loss}
                )
            else:
                closing_lines.append(
                    {'account_code': reserves_account.code, 'debit': abs(profit_or_loss), 'credit': Decimal('0')}
                )

            if closing_lines:
                create_journal_entry(
                    entry_date=financial_year.end_date,
                    voucher_type='journal',
                    branch=branch,
                    narration=f'Year-end P&L transfer for {financial_year.fy_code}',
                    lines=closing_lines,
                    user=user,
                    reference_type='year_end',
                )

        # Zero out income and expense current_balance after the closing entry.
        # The closing entry already reversed their GL balances; this resets the
        # running counter so the new financial year starts clean.
        for account in list(income_accounts) + list(expense_accounts):
            if account.current_balance != Decimal('0'):
                account.current_balance = Decimal('0')
                account.save(update_fields=['current_balance'])
                pl_count += 1

        # Asset/liability/equity current_balance is already maintained in
        # real-time by create_journal_entry, so no recalculation is needed.
        ob_count = ChartOfAccounts.objects.filter(
            account_group__in=['asset', 'liability', 'equity'],
        ).count()

        log.pl_accounts_zeroed = pl_count
        log.opening_balances_updated = ob_count
        log.profit_or_loss = profit_or_loss
        log.status = 'completed'
        log.completed_at = timezone.now()
        log.save()

        financial_year.is_closed = True
        financial_year.closed_by = user
        financial_year.closed_at = timezone.now()
        financial_year.save()

        return log
    except Exception as e:
        log.status = 'failed'
        log.error_log = str(e)
        log.completed_at = timezone.now()
        log.save()
        raise


def _accrue_savings_interest(branch, processing_date):
    import calendar

    from apps.savings.models import SavingsAccount

    count = 0
    days_in_year = Decimal('366' if calendar.isleap(processing_date.year) else '365')
    accounts = SavingsAccount.objects.filter(branch=branch, status='active', interest_rate__gt=0)
    for account in accounts:
        daily_rate = account.interest_rate / (Decimal('100') * days_in_year)
        daily_interest = (account.current_balance * daily_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        account.accrued_interest = (account.accrued_interest or Decimal('0')) + daily_interest
        account.last_interest_calculated_date = processing_date
        account.save(update_fields=['accrued_interest', 'last_interest_calculated_date'])
        count += 1
    return count


def _accrue_loan_interest(branch, processing_date):
    from apps.loans.models import LoanAccount

    count = 0
    loans = LoanAccount.objects.filter(branch=branch, status='disbursed')
    for loan in loans:
        daily_rate = loan.interest_rate / Decimal('365') / Decimal('100')
        daily_interest = loan.outstanding_principal * daily_rate
        loan.outstanding_interest += daily_interest
        loan.last_interest_calculated_date = processing_date
        loan.save(update_fields=['outstanding_interest', 'last_interest_calculated_date'])
        count += 1
    return count


def _mark_overdue_loans(branch, processing_date):
    from apps.loans.models import EMISchedule

    overdue = EMISchedule.objects.filter(
        loan__branch=branch,
        loan__status='disbursed',
        due_date__lt=processing_date,
        status='pending',
    )
    count = overdue.update(status='overdue')
    return count


def _mark_npa_loans(branch, processing_date):
    from apps.loans.models import LoanAccount

    count = 0
    loans = LoanAccount.objects.filter(branch=branch, status='disbursed')
    for loan in loans:
        threshold = loan.loan_product.npa_days_threshold
        overdue_emis = loan.emi_schedule.filter(status='overdue')
        if overdue_emis.exists():
            oldest = overdue_emis.order_by('due_date').first()
            days_overdue = (processing_date - oldest.due_date).days
            loan.overdue_days = days_overdue
            if days_overdue >= threshold and loan.status != 'npa':
                loan.status = 'npa'
                count += 1
            loan.save(update_fields=['overdue_days', 'status'])
    return count


def _auto_cashbook_posting(branch, processing_date, user):
    """Aggregate day's journal entries into CashbookMaster.

    Individual transactions already create journal entries at transaction
    time. This step aggregates them into a daily cashbook summary with
    opening/closing balances per branch.
    """
    from apps.accounting.models import CashbookMaster, JournalEntry, JournalLine

    entries = JournalEntry.objects.filter(
        branch=branch,
        entry_date=processing_date,
        is_reversed=False,
    )
    entries_count = entries.count()

    agg = JournalLine.objects.filter(
        journal_entry__in=entries,
    ).aggregate(
        receipt_total=Sum(
            'debit_amount',
            filter=Q(journal_entry__voucher_type='receipt'),
            default=Decimal('0'),
        ),
        payment_total=Sum(
            'credit_amount',
            filter=Q(journal_entry__voucher_type='payment'),
            default=Decimal('0'),
        ),
        receipt_cash=Sum(
            'debit_amount',
            filter=Q(journal_entry__voucher_type='receipt', journal_entry__payment_mode='cash'),
            default=Decimal('0'),
        ),
        receipt_transfer=Sum(
            'debit_amount',
            filter=Q(journal_entry__voucher_type='receipt', journal_entry__payment_mode='transfer'),
            default=Decimal('0'),
        ),
        payment_cash=Sum(
            'credit_amount',
            filter=Q(journal_entry__voucher_type='payment', journal_entry__payment_mode='cash'),
            default=Decimal('0'),
        ),
        payment_transfer=Sum(
            'credit_amount',
            filter=Q(journal_entry__voucher_type='payment', journal_entry__payment_mode='transfer'),
            default=Decimal('0'),
        ),
    )
    receipt_total = agg['receipt_total'] or Decimal('0')
    payment_total = agg['payment_total'] or Decimal('0')

    previous_cb = (
        CashbookMaster.objects.filter(
            branch=branch,
            txn_date__lt=processing_date,
            is_closed=True,
        )
        .order_by('-txn_date')
        .first()
    )
    opening = previous_cb.closing_balance if previous_cb else Decimal('0')

    _cb, _created = CashbookMaster.objects.update_or_create(
        branch=branch,
        txn_date=processing_date,
        defaults={
            'opening_balance': opening,
            'total_receipts': receipt_total,
            'total_payments': payment_total,
            'receipt_cash': agg['receipt_cash'] or Decimal('0'),
            'receipt_transfer': agg['receipt_transfer'] or Decimal('0'),
            'payment_cash': agg['payment_cash'] or Decimal('0'),
            'payment_transfer': agg['payment_transfer'] or Decimal('0'),
            'closing_balance': opening + receipt_total - payment_total,
            'is_closed': True,
            'closed_by': user,
        },
    )

    return entries_count
