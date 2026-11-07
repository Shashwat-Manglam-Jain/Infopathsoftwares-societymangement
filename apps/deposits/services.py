from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction

from apps.deposits.models import FixedDeposit, RDInstallment, RecurringDeposit


def calculate_fd_maturity(principal, annual_rate, tenure_days, compounding='quarterly'):
    principal = Decimal(str(principal))
    rate = Decimal(str(annual_rate)) / Decimal('100')

    if compounding == 'cumulative':
        interest = principal * rate * Decimal(str(tenure_days)) / Decimal('365')
        return (principal + interest).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    compounds_per_year = {
        'quarterly': 4,
        'half_yearly': 2,
        'yearly': 1,
    }
    n = Decimal(str(compounds_per_year.get(compounding, 4)))
    t = Decimal(str(tenure_days)) / Decimal('365')
    amount = principal * (Decimal('1') + rate / n) ** (n * t)
    return amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def create_fd(
    member,
    product,
    amount,
    tenure_days,
    branch,
    user,
    is_auto_renew=False,
    linked_savings_account=None,
    is_senior=False,
):
    amount = Decimal(str(amount))

    if amount < product.min_amount or amount > product.max_amount:
        raise ValueError(f'Amount must be between {product.min_amount} and {product.max_amount}')
    if tenure_days < product.min_tenure_days or tenure_days > product.max_tenure_days:
        raise ValueError(f'Tenure must be between {product.min_tenure_days} and {product.max_tenure_days} days')

    rate = product.get_rate_for_tenure(tenure_days, is_senior)
    if rate is None:
        raise ValueError('No interest rate slab found for this tenure')
    rate = Decimal(str(rate))

    bonus = member.get_fd_interest_bonus()
    if bonus > Decimal('0'):
        rate += bonus

    maturity_amount = calculate_fd_maturity(amount, rate, tenure_days, product.compounding)
    start = date.today()
    maturity_date = start + timedelta(days=tenure_days)

    with transaction.atomic():
        fd_no = _generate_fd_no(branch)
        cert_no = f'FDC-{fd_no}'

        fd = FixedDeposit.objects.create(
            member=member,
            branch=branch,
            fd_product=product,
            fd_no=fd_no,
            deposit_amount=amount,
            interest_rate=rate,
            senior_citizen_rate=rate if is_senior else Decimal('0'),
            start_date=start,
            maturity_date=maturity_date,
            tenure_days=tenure_days,
            maturity_amount=maturity_amount,
            is_auto_renew=is_auto_renew,
            compounding_type=product.compounding,
            linked_savings_account=linked_savings_account,
            certificate_no=cert_no,
            created_by=user,
        )

        _create_fd_creation_journal(fd, branch, user)
        return fd


def mature_fd(fd, user):
    if fd.status != 'active':
        raise ValueError('FD is not active')
    if date.today() < fd.maturity_date:
        raise ValueError('FD has not matured yet')

    with transaction.atomic():
        fd.status = 'matured'
        fd.accrued_interest = fd.maturity_amount - fd.deposit_amount
        fd.save(update_fields=['status', 'accrued_interest'])

        if fd.linked_savings_account:
            from apps.savings.services import deposit as savings_deposit

            savings_deposit(
                fd.linked_savings_account,
                fd.maturity_amount,
                fd.branch,
                user,
                payment_mode='transfer',
                narration=f'FD maturity credit {fd.fd_no}',
            )
        _create_fd_maturity_journal(fd, fd.branch, user)

        if fd.is_auto_renew:
            return renew_fd(fd, user)
        return fd


def premature_close_fd(fd, user):
    if fd.status != 'active':
        raise ValueError('FD is not active')

    with transaction.atomic():
        held_days = (date.today() - fd.start_date).days
        penalty_rate = fd.fd_product.premature_penalty_percent
        effective_rate = fd.interest_rate - penalty_rate
        if effective_rate < 0:
            effective_rate = Decimal('0')

        premature_amount = calculate_fd_maturity(
            fd.deposit_amount,
            effective_rate,
            held_days,
            fd.compounding_type,
        )

        fd.status = 'prematurely_closed'
        fd.premature_closure_date = date.today()
        fd.premature_amount = premature_amount
        fd.accrued_interest = premature_amount - fd.deposit_amount
        fd.save()

        _create_fd_maturity_journal(fd, fd.branch, user, amount=premature_amount)
        return fd


def renew_fd(fd, user):
    return create_fd(
        member=fd.member,
        product=fd.fd_product,
        amount=fd.maturity_amount,
        tenure_days=fd.tenure_days,
        branch=fd.branch,
        user=user,
        is_auto_renew=fd.is_auto_renew,
        linked_savings_account=fd.linked_savings_account,
    )


def create_rd(member, monthly_installment, tenure_months, interest_rate, branch, user, linked_savings_account=None):
    monthly_installment = Decimal(str(monthly_installment))
    interest_rate = Decimal(str(interest_rate))

    maturity_amount = _calculate_rd_maturity(monthly_installment, interest_rate, tenure_months)
    start = date.today()
    maturity_date = date(
        start.year + (start.month + tenure_months - 1) // 12,
        (start.month + tenure_months - 1) % 12 + 1,
        min(start.day, 28),
    )

    with transaction.atomic():
        rd_no = _generate_rd_no(branch)
        rd = RecurringDeposit.objects.create(
            member=member,
            branch=branch,
            rd_no=rd_no,
            monthly_installment=monthly_installment,
            interest_rate=interest_rate,
            start_date=start,
            maturity_date=maturity_date,
            tenure_months=tenure_months,
            maturity_amount=maturity_amount,
            linked_savings_account=linked_savings_account,
            created_by=user,
        )

        for i in range(1, tenure_months + 1):
            m = (start.month + i - 1) % 12 + 1
            y = start.year + (start.month + i - 1) // 12
            due = date(y, m, min(start.day, 28))
            RDInstallment.objects.create(
                rd=rd,
                installment_no=i,
                due_date=due,
                amount=monthly_installment,
            )

        return rd


def collect_rd_installment(rd, amount, branch, user):
    amount = Decimal(str(amount))
    installment = (
        RDInstallment.objects.filter(
            rd=rd,
            status__in=('pending', 'overdue'),
        )
        .order_by('installment_no')
        .first()
    )

    if not installment:
        raise ValueError('No pending installment found')

    with transaction.atomic():
        installment.paid_amount = amount
        installment.paid_date = date.today()
        installment.branch = branch
        installment.status = 'paid'
        installment.save()

        _create_rd_journal(rd, amount, branch, user, installment)
        return installment


def mature_rd(rd, user):
    if rd.status != 'active':
        raise ValueError('RD is not active')

    pending = RDInstallment.objects.filter(rd=rd, status__in=('pending', 'overdue')).count()
    if pending > 0:
        raise ValueError(f'{pending} installments still unpaid')

    with transaction.atomic():
        rd.status = 'matured'
        rd.save(update_fields=['status'])

        if rd.linked_savings_account:
            from apps.savings.services import deposit as savings_deposit

            savings_deposit(
                rd.linked_savings_account,
                rd.maturity_amount,
                rd.branch,
                user,
                payment_mode='transfer',
                narration=f'RD maturity credit {rd.rd_no}',
            )
        return rd


def _calculate_rd_maturity(installment, annual_rate, tenure_months):
    quarterly_rate = Decimal(str(annual_rate)) / Decimal('400')
    total = Decimal('0')
    for i in range(tenure_months):
        months_remaining = tenure_months - i
        quarters = Decimal(str(months_remaining)) / Decimal('3')
        amount = installment * (Decimal('1') + quarterly_rate) ** quarters
        total += amount
    return total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _generate_fd_no(branch):
    last = FixedDeposit.objects.filter(fd_no__startswith=f'FD-{branch.branch_code}').order_by('-fd_no').first()
    if last:
        seq = int(last.fd_no.split('-')[-1]) + 1
    else:
        seq = 1
    return f'FD-{branch.branch_code}-{seq:06d}'


def _generate_rd_no(branch):
    last = RecurringDeposit.objects.filter(rd_no__startswith=f'RD-{branch.branch_code}').order_by('-rd_no').first()
    if last:
        seq = int(last.rd_no.split('-')[-1]) + 1
    else:
        seq = 1
    return f'RD-{branch.branch_code}-{seq:06d}'


def _create_fd_creation_journal(fd, branch, user):
    from apps.accounting.services import create_journal_entry
    from apps.savings.services import _get_cash_code

    create_journal_entry(
        entry_date=fd.start_date,
        voucher_type='receipt',
        branch=branch,
        narration=f'FD creation {fd.fd_no}',
        lines=[
            {'account_code': _get_cash_code(branch), 'debit': fd.deposit_amount, 'credit': Decimal('0')},
            {'account_code': '2002', 'debit': Decimal('0'), 'credit': fd.deposit_amount},
        ],
        user=user,
        reference_type='fd_creation',
        reference_id=fd.pk,
    )


def _create_fd_maturity_journal(fd, branch, user, amount=None):
    from apps.accounting.services import create_journal_entry
    from apps.savings.services import _get_cash_code

    payout = amount or fd.maturity_amount
    interest = payout - fd.deposit_amount
    lines = [
        {'account_code': '2002', 'debit': fd.deposit_amount, 'credit': Decimal('0')},
    ]
    if interest > 0:
        lines.append({'account_code': '4002', 'debit': interest, 'credit': Decimal('0')})
    lines.append({'account_code': _get_cash_code(branch), 'debit': Decimal('0'), 'credit': payout})
    create_journal_entry(
        entry_date=date.today(),
        voucher_type='payment',
        branch=branch,
        narration=f'FD maturity/closure {fd.fd_no}',
        lines=lines,
        user=user,
        reference_type='fd_maturity',
        reference_id=fd.pk,
    )


def _create_rd_journal(rd, amount, branch, user, installment):
    from apps.accounting.services import create_journal_entry
    from apps.savings.services import _get_cash_code

    create_journal_entry(
        entry_date=date.today(),
        voucher_type='receipt',
        branch=branch,
        narration=f'RD installment {rd.rd_no} #{installment.installment_no}',
        lines=[
            {'account_code': _get_cash_code(branch), 'debit': amount, 'credit': Decimal('0')},
            {'account_code': '2003', 'debit': Decimal('0'), 'credit': amount},
        ],
        user=user,
        reference_type='rd_installment',
        reference_id=installment.pk,
    )
