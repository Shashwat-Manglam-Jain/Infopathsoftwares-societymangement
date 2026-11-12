from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.db import models, transaction

from apps.core.date_utils import get_transaction_date
from apps.loans.models import EMISchedule, LoanAccount, LoanRepayment


def calculate_emi(principal, annual_rate, tenure_months, interest_type='reducing_monthly'):
    principal = Decimal(str(principal))
    annual_rate = Decimal(str(annual_rate))
    tenure_months = int(tenure_months)

    if interest_type == 'flat':
        total_interest = principal * annual_rate * Decimal(str(tenure_months)) / (Decimal('12') * Decimal('100'))
        emi = (principal + total_interest) / Decimal(str(tenure_months))
        return emi.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    monthly_rate = annual_rate / (Decimal('12') * Decimal('100'))
    if monthly_rate == 0:
        return (principal / Decimal(str(tenure_months))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    factor = (Decimal('1') + monthly_rate) ** tenure_months
    emi = principal * monthly_rate * factor / (factor - Decimal('1'))
    return emi.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def generate_emi_schedule(loan):
    EMISchedule.objects.filter(loan=loan).delete()

    principal = loan.disbursed_amount
    rate = loan.interest_rate
    tenure = loan.tenure_months
    interest_type = loan.loan_product.interest_type
    emi = calculate_emi(principal, rate, tenure, interest_type)
    loan.emi_amount = emi
    loan.save(update_fields=['emi_amount', 'updated_at'])

    schedule = []
    outstanding = principal
    start_date = loan.disbursed_date
    original_day = start_date.day
    monthly_rate = rate / (Decimal('12') * Decimal('100'))
    total_interest = Decimal('0')

    import calendar

    for i in range(1, tenure + 1):
        next_month = start_date.month + i
        year_offset = (next_month - 1) // 12
        month = (next_month - 1) % 12 + 1
        year = start_date.year + year_offset
        last_day = calendar.monthrange(year, month)[1]
        due_date = date(year, month, min(original_day, last_day))

        if interest_type == 'flat':
            interest_component = (principal * rate) / (Decimal('12') * Decimal('100'))
            interest_component = interest_component.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            principal_component = emi - interest_component
        else:
            interest_component = (outstanding * monthly_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            principal_component = emi - interest_component

        if i == tenure:
            principal_component = outstanding
            emi_total = principal_component + interest_component
        else:
            emi_total = emi

        outstanding -= principal_component
        total_interest += interest_component

        entry = EMISchedule.objects.create(
            loan=loan,
            installment_no=i,
            due_date=due_date,
            principal_component=principal_component,
            interest_component=interest_component,
            total_emi=emi_total,
        )
        schedule.append(entry)

    loan.total_interest_payable = total_interest
    loan.save(update_fields=['total_interest_payable', 'updated_at'])
    return schedule


@transaction.atomic
def approve_loan(loan, approved_amount, approved_by):
    if loan.status != 'applied':
        raise ValueError('Loan is not in applied status')

    product = loan.loan_product
    if product.requires_guarantor:
        from apps.loans.models import LoanGuarantor

        count = LoanGuarantor.objects.filter(loan=loan).count()
        if count < product.min_guarantors:
            raise ValueError(
                f'Cannot approve: this loan requires at least {product.min_guarantors} guarantor(s). '
                f'Only {count} assigned.'
            )

    if product.requires_collateral:
        from apps.loans.models import LoanCollateral

        collateral_count = LoanCollateral.objects.filter(loan=loan).count()
        if collateral_count == 0:
            raise ValueError(
                'Cannot approve: this loan product requires collateral. Add at least one collateral before approving.'
            )

    loan.status = 'approved'
    loan.approved_date = get_transaction_date(loan.branch)
    loan.approved_amount = Decimal(str(approved_amount))
    loan.approved_by = approved_by
    loan.save(
        update_fields=[
            'status',
            'approved_date',
            'approved_amount',
            'approved_by',
            'updated_at',
        ]
    )
    return loan


def reject_loan(loan, remarks, user):
    if loan.status != 'applied':
        raise ValueError('Loan is not in applied status')
    loan.status = 'rejected'
    loan.remarks = remarks
    loan.save(update_fields=['status', 'remarks', 'updated_at'])
    return loan


def disburse_loan(loan, branch, user):
    if loan.status != 'approved':
        raise ValueError('Loan is not in approved status')
    if loan.approved_amount <= Decimal('0'):
        raise ValueError('Approved amount must be greater than zero')

    product = loan.loan_product
    if loan.approved_amount > product.max_amount:
        raise ValueError(
            f'Approved amount ₹{loan.approved_amount} exceeds product limit ₹{product.max_amount}'
        )
    if product.requires_guarantor:
        from apps.loans.models import LoanGuarantor

        count = LoanGuarantor.objects.filter(loan=loan).count()
        if count < product.min_guarantors:
            raise ValueError(
                f'This loan requires at least {product.min_guarantors} guarantor(s). '
                f'Only {count} assigned. Add guarantors before disbursing.'
            )

    with transaction.atomic():
        import calendar

        txn_date = get_transaction_date(branch)
        loan.status = 'disbursed'
        loan.disbursed_date = txn_date
        loan.disbursed_amount = loan.approved_amount
        loan.outstanding_principal = loan.approved_amount
        loan.bal_repayment = loan.approved_amount
        loan.last_interest_calculated_date = txn_date

        start = txn_date
        next_month = start.month + 1
        year_offset = (next_month - 1) // 12
        month = (next_month - 1) % 12 + 1
        year = start.year + year_offset
        last_day = calendar.monthrange(year, month)[1]
        loan.date_of_first_recovery = date(year, month, min(start.day, last_day))

        exp_month = start.month + loan.tenure_months
        exp_year_offset = (exp_month - 1) // 12
        exp_m = (exp_month - 1) % 12 + 1
        exp_y = start.year + exp_year_offset
        exp_last = calendar.monthrange(exp_y, exp_m)[1]
        loan.loan_expiry_date = date(exp_y, exp_m, min(start.day, exp_last))

        loan.save(
            update_fields=[
                'status',
                'disbursed_date',
                'disbursed_amount',
                'outstanding_principal',
                'bal_repayment',
                'last_interest_calculated_date',
                'date_of_first_recovery',
                'loan_expiry_date',
                'updated_at',
            ]
        )

        generate_emi_schedule(loan)

        processing_fee = (loan.disbursed_amount * loan.loan_product.processing_fee_percent / Decimal('100')).quantize(
            Decimal('0.01'),
            rounding=ROUND_HALF_UP,
        )

        _create_disbursement_journal(loan, branch, user, processing_fee)
        return loan


def collect_emi(loan, amount, branch, user, payment_mode='cash'):
    amount = Decimal(str(amount))
    if loan.status not in ('disbursed', 'npa'):
        raise ValueError('Loan is not in disbursed status')
    if amount <= 0:
        raise ValueError('Amount must be positive')
    total_outstanding = loan.outstanding_principal + loan.outstanding_interest + loan.overdue_amount
    if amount > total_outstanding and total_outstanding > 0:
        raise ValueError(
            f'Payment ₹{amount} exceeds total outstanding ₹{total_outstanding}. '
            f'Maximum collectible: ₹{total_outstanding}'
        )

    with transaction.atomic():
        txn_date = get_transaction_date(branch)
        penalty_adjusted = Decimal('0')
        interest_adjusted = Decimal('0')
        principal_adjusted = Decimal('0')
        remaining = amount

        if loan.overdue_amount > 0:
            penalty = min(remaining, loan.overdue_amount)
            penalty_adjusted = penalty
            remaining -= penalty

        if loan.outstanding_interest > 0:
            interest = min(remaining, loan.outstanding_interest)
            interest_adjusted = interest
            remaining -= interest

        principal_adjusted = remaining
        loan.outstanding_principal -= principal_adjusted
        loan.outstanding_interest -= interest_adjusted
        loan.overdue_amount -= penalty_adjusted
        loan.bal_repayment = max(loan.outstanding_principal, Decimal('0'))
        loan.bal_interest = max(loan.outstanding_interest, Decimal('0'))
        loan.bal_penal = max(loan.overdue_amount, Decimal('0'))

        emi_entry = EMISchedule.objects.filter(
            loan=loan,
            status__in=('pending', 'overdue', 'partially_paid'),
        ).first()
        if emi_entry:
            emi_entry.paid_amount += amount
            emi_entry.paid_date = txn_date
            emi_entry.branch = branch
            if emi_entry.paid_amount >= emi_entry.total_emi:
                emi_entry.status = 'paid'
            else:
                emi_entry.status = 'partially_paid'
            emi_entry.save()

        if loan.outstanding_principal <= 0:
            loan.outstanding_principal = Decimal('0')
            loan.status = 'closed'
            loan.closure_date = txn_date
            loan.closure_type = 'normal'

        if loan.overdue_days > 0 and loan.overdue_amount <= 0:
            loan.overdue_days = 0

        loan.save()

        receipt_no = f'LR-{loan.loan_no}-{LoanRepayment.objects.filter(loan=loan).count() + 1:04d}'
        repayment = LoanRepayment.objects.create(
            loan=loan,
            branch=branch,
            payment_date=txn_date,
            amount=amount,
            principal_adjusted=principal_adjusted,
            interest_adjusted=interest_adjusted,
            penalty_adjusted=penalty_adjusted,
            excess_amount=Decimal('0'),
            payment_mode=payment_mode,
            receipt_no=receipt_no,
            emi_schedule=emi_entry,
            created_by=user,
        )

        _create_emi_collection_journal(loan, repayment, branch, user)
        return repayment


def calculate_loan_interest(loan, for_date):
    if loan.outstanding_principal <= 0 or loan.interest_rate <= 0:
        return Decimal('0.00')
    daily_rate = loan.interest_rate / (Decimal('365') * Decimal('100'))
    interest = (loan.outstanding_principal * daily_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return interest


def prepay_loan(loan, amount, branch, user):
    amount = Decimal(str(amount))
    if amount > loan.outstanding_principal + loan.outstanding_interest:
        raise ValueError('Prepayment amount exceeds outstanding')
    return collect_emi(loan, amount, branch, user)


def close_loan(loan, user):
    if loan.outstanding_principal > 0 or loan.outstanding_interest > 0:
        raise ValueError('Outstanding balance exists')
    loan.status = 'closed'
    loan.closure_date = get_transaction_date(loan.branch)
    loan.closure_type = 'normal'
    loan.save(update_fields=['status', 'closure_date', 'closure_type', 'updated_at'])
    return loan


def mark_overdue(loan):
    today = date.today()
    overdue_emis = EMISchedule.objects.filter(
        loan=loan,
        due_date__lt=today,
        status__in=('pending', 'partially_paid'),
    )
    if not overdue_emis.exists():
        return

    oldest_overdue = overdue_emis.order_by('due_date').first()
    loan.overdue_days = (today - oldest_overdue.due_date).days
    loan.overdue_amount = sum((e.total_emi - e.paid_amount) for e in overdue_emis)
    loan.save(update_fields=['overdue_days', 'overdue_amount', 'updated_at'])

    overdue_emis.filter(status='pending').update(status='overdue')


def mark_npa(loan):
    if loan.overdue_days >= loan.loan_product.npa_days_threshold and loan.status == 'disbursed':
        loan.status = 'npa'
        loan.save(update_fields=['status', 'updated_at'])


def _create_disbursement_journal(loan, branch, user, processing_fee):
    from apps.accounting.services import create_journal_entry
    from apps.core.gl_utils import get_account_gl_code, get_gl_code

    loan_code = get_account_gl_code(loan, 'loan', '1003')
    disbursed = loan.disbursed_amount
    cash_credit = disbursed - processing_fee if processing_fee > 0 else disbursed

    lines = [
        {'account_code': loan_code, 'debit': disbursed, 'credit': Decimal('0')},
        {'account_code': _get_cash_code(branch), 'debit': Decimal('0'), 'credit': cash_credit},
    ]
    if processing_fee > 0:
        from apps.accounting.models import ChartOfAccounts

        fee_income_code = get_gl_code('processing_fee_income', '3002')
        if ChartOfAccounts.objects.filter(code=fee_income_code).exists():
            lines.append({'account_code': fee_income_code, 'debit': Decimal('0'), 'credit': processing_fee})
        else:
            cash_credit = disbursed
            lines[1] = {'account_code': _get_cash_code(branch), 'debit': Decimal('0'), 'credit': cash_credit}
    create_journal_entry(
        entry_date=loan.disbursed_date,
        voucher_type='payment',
        branch=branch,
        narration=f'Loan disbursement {loan.loan_no} to {loan.member}',
        lines=lines,
        user=user,
        reference_type='loan_disbursement',
        reference_id=loan.pk,
    )


def _create_emi_collection_journal(loan, repayment, branch, user):
    from apps.accounting.services import create_journal_entry
    from apps.core.gl_utils import get_account_gl_code, get_gl_code

    loan_code = get_account_gl_code(loan, 'loan', '1003')
    interest_income_code = get_gl_code('interest_received', '3001')
    penal_income_code = get_gl_code('interest_receivable', '3003')

    lines = [
        {'account_code': _get_cash_code(branch), 'debit': repayment.amount, 'credit': Decimal('0')},
    ]
    if repayment.principal_adjusted > 0:
        lines.append(
            {'account_code': loan_code, 'debit': Decimal('0'), 'credit': repayment.principal_adjusted},
        )
    if repayment.interest_adjusted > 0:
        lines.append(
            {'account_code': interest_income_code, 'debit': Decimal('0'), 'credit': repayment.interest_adjusted},
        )
    if repayment.penalty_adjusted > 0:
        lines.append(
            {'account_code': penal_income_code, 'debit': Decimal('0'), 'credit': repayment.penalty_adjusted},
        )
    create_journal_entry(
        entry_date=repayment.payment_date,
        voucher_type='receipt',
        branch=branch,
        narration=f'EMI collection {loan.loan_no}',
        lines=lines,
        user=user,
        reference_type='emi_payment',
        reference_id=repayment.pk,
    )


def _get_cash_code(branch):
    from apps.accounting.models import ChartOfAccounts

    cash = ChartOfAccounts.objects.filter(account_type='cash', branch=branch).first()
    return cash.code if cash else '1001'


def get_active_guarantee_count(member):
    """Count how many active (non-zero balance) loans this member is guarantor for."""
    from apps.loans.models import LoanGuarantor

    return LoanGuarantor.objects.filter(
        guarantor_member=member,
        loan__status__in=['disbursed', 'npa'],
        loan__outstanding_principal__gt=Decimal('0'),
    ).count()


def validate_loan_application(member, loan_product, amount):
    """Validate if a member can apply for a loan."""
    errors = []
    amount = Decimal(str(amount))

    from apps.shares.models import ShareHolding

    if not ShareHolding.objects.filter(member=member, status='active', share_count__gt=0).exists():
        errors.append('Member must have active shares to apply for a loan.')

    if not loan_product.allow_multiple:
        active_loans = (
            LoanAccount.objects.filter(
                member=member,
                loan_product__loan_category__in=['regular', 'emergency'],
                status__in=['applied', 'approved', 'disbursed'],
            )
            .filter(
                models.Q(status__in=['applied', 'approved'])
                | models.Q(status='disbursed', outstanding_principal__gt=Decimal('0'))
            )
            .exists()
        )
        if active_loans:
            errors.append(
                f'Member already has an active non-mortgage loan. '
                f'Close existing loan (balance must be nil) before applying for {loan_product.name}.'
            )

    if loan_product.max_loan_to_deposit_ratio and loan_product.mortgage_type == 'fixed_deposit':
        from django.db.models import Sum

        from apps.deposits.models import FixedDeposit

        total_fd = FixedDeposit.objects.filter(
            member=member,
            status='active',
        ).aggregate(total=Sum('deposit_amount'))['total'] or Decimal('0')
        max_loan = total_fd * loan_product.max_loan_to_deposit_ratio / Decimal('100')
        if amount > max_loan:
            errors.append(f'Loan amount exceeds {loan_product.max_loan_to_deposit_ratio}% of FD value ({max_loan}).')

    return errors


def add_standing_instruction(loan, charge_type, amount, branch, narration, created_by):
    """Add a standing instruction (fee/charge) to a loan account."""
    from apps.loans.models import StandingInstruction

    amount = Decimal(str(amount))
    txn_date = get_transaction_date(branch)

    si = StandingInstruction.objects.create(
        loan=loan,
        branch=branch,
        charge_type=charge_type,
        amount=amount,
        charge_date=txn_date,
        narration=narration,
        created_by=created_by,
    )

    loan.outstanding_principal += amount
    loan.save(update_fields=['outstanding_principal', 'updated_at'])

    from apps.accounting.models import ChartOfAccounts
    from apps.accounting.services import create_journal_entry
    from apps.core.gl_utils import get_account_gl_code, get_gl_code

    loan_code = get_account_gl_code(loan, 'loan', '1003')
    fee_income_code = get_gl_code('interest_received', '4004')

    if ChartOfAccounts.objects.filter(code__in=[loan_code, fee_income_code]).count() == 2:
        create_journal_entry(
            entry_date=txn_date,
            voucher_type='journal',
            branch=branch,
            narration=narration,
            lines=[
                {'account_code': loan_code, 'debit': amount, 'credit': Decimal('0')},
                {'account_code': fee_income_code, 'debit': Decimal('0'), 'credit': amount},
            ],
            user=created_by,
            reference_type='standing_instruction',
            reference_id=si.pk,
        )

    return si


def reverse_repayment(repayment, user):
    from apps.accounting.models import JournalEntry
    from apps.accounting.services import reverse_journal_entry

    loan = repayment.loan

    with transaction.atomic():
        loan.outstanding_principal += repayment.principal_adjusted
        loan.outstanding_interest += repayment.interest_adjusted
        loan.overdue_amount += repayment.penalty_adjusted
        loan.bal_repayment = loan.outstanding_principal
        loan.bal_interest = loan.outstanding_interest
        loan.bal_penal = loan.overdue_amount

        if loan.status == 'closed':
            loan.status = 'disbursed'
            loan.closure_date = None
            loan.closure_type = ''
        loan.save()

        if repayment.emi_schedule:
            emi = repayment.emi_schedule
            emi.paid_amount -= repayment.amount
            if emi.paid_amount <= 0:
                emi.paid_amount = Decimal('0')
                emi.status = 'pending'
                emi.paid_date = None
            else:
                emi.status = 'partially_paid'
            emi.save()

        original_journal = JournalEntry.objects.filter(
            reference_type='emi_collection',
            reference_id=repayment.pk,
            is_reversed=False,
        ).first()
        if original_journal:
            reverse_journal_entry(original_journal, user)

        repayment.delete()

        return True
