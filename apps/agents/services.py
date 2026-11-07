from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from .models import AgentCollection, PigmmyAccount, PigmmyTransaction


@transaction.atomic
def create_pigmmy_account(
    member,
    agent,
    branch,
    installment_amount,
    deposit_period_months,
    interest_rate,
    deposit_type='daily',
    linked_savings=None,
    created_by=None,
):
    if PigmmyAccount.objects.filter(member=member, status='active').exists():
        raise ValueError('Member already has an active pigmmy account. Only one per member is allowed.')

    from apps.savings.models import SavingsAccount

    if not SavingsAccount.objects.filter(member=agent.member, status='active', account_type='savings').exists():
        raise ValueError('Agent must have an active savings account.')
    if not SavingsAccount.objects.filter(member=agent.member, status='active', account_type='security').exists():
        raise ValueError('Agent must have an active security deposit account.')

    last = PigmmyAccount.objects.order_by('-id').first()
    if last:
        try:
            seq = int(''.join(filter(str.isdigit, last.account_no))) + 1
        except ValueError:
            seq = PigmmyAccount.objects.count() + 1
    else:
        seq = 1
    account_no = f'PG{seq:06d}'

    if deposit_type == 'daily':
        total_installments = deposit_period_months * 26
    elif deposit_type == 'weekly':
        total_installments = deposit_period_months * 4
    else:
        total_installments = deposit_period_months

    monthly_rate = Decimal(str(interest_rate)) / Decimal('1200')
    maturity_amount = Decimal('0')
    for i in range(total_installments):
        remaining_months = Decimal(str(deposit_period_months)) - (Decimal(str(i)) * Decimal(str(deposit_period_months)) / Decimal(str(total_installments)))
        maturity_amount += installment_amount * (Decimal('1') + monthly_rate) ** remaining_months
    maturity_amount = maturity_amount.quantize(Decimal('0.01'))

    today = date.today()
    mat_month = today.month + deposit_period_months
    mat_year = today.year + (mat_month - 1) // 12
    mat_month = (mat_month - 1) % 12 + 1
    import calendar

    mat_day = min(today.day, calendar.monthrange(mat_year, mat_month)[1])
    maturity_date = date(mat_year, mat_month, mat_day)

    account = PigmmyAccount.objects.create(
        account_no=account_no,
        member=member,
        branch=branch,
        agent=agent,
        linked_savings_account=linked_savings,
        deposit_type=deposit_type,
        installment_amount=installment_amount,
        deposit_period_months=deposit_period_months,
        interest_rate=interest_rate,
        opening_date=today,
        maturity_date=maturity_date,
        maturity_amount=maturity_amount,
        total_installments=total_installments,
        status='active',
        created_by=created_by,
    )
    return account


@transaction.atomic
def record_agent_collection(agent, collection_date, client_payments, branch, created_by):
    """Record daily collection by an agent for multiple clients.

    client_payments: list of dicts [{'account_id': int, 'amount': Decimal}, ...]
    """
    collection, _ = AgentCollection.objects.get_or_create(
        agent=agent,
        collection_date=collection_date,
        defaults={
            'branch': branch,
            'status': 'open',
        },
    )

    total_collected = Decimal('0.00')
    clients_collected = 0

    for payment in client_payments:
        account = PigmmyAccount.objects.select_for_update().get(id=payment['account_id'])
        amount = Decimal(str(payment['amount']))

        if amount <= 0:
            continue

        new_balance = account.current_balance + amount
        PigmmyTransaction.objects.create(
            account=account,
            branch=branch,
            txn_date=collection_date,
            amount=amount,
            running_balance=new_balance,
            installment_no=account.paid_installments + 1,
            narration=f'Collection by Agent {agent.agent_code}',
            collected_by=agent,
            created_by=created_by,
        )

        account.current_balance = new_balance
        account.total_deposited += amount
        account.paid_installments += 1
        account.save()

        total_collected += amount
        clients_collected += 1

    collection.total_clients_collected = clients_collected
    collection.collected_amount = total_collected
    collection.deposited_amount = total_collected
    collection.status = 'submitted'
    collection.save()

    from apps.accounting.models import ChartOfAccounts
    from apps.accounting.services import create_journal_entry

    cash_account = ChartOfAccounts.objects.filter(
        code__startswith='1',
        name__icontains='cash',
    ).first()
    pigmmy_head = (
        ChartOfAccounts.objects.filter(
            name__icontains='pigm',
        ).first()
        or ChartOfAccounts.objects.filter(
            name__icontains='daily',
        ).first()
    )

    if cash_account and pigmmy_head:
        create_journal_entry(
            entry_date=collection_date,
            voucher_type='receipt',
            branch=branch,
            narration=f'Pigmmy collection by Agent {agent.agent_code} - {collection_date}',
            lines=[
                {'account_code': cash_account.code, 'debit': total_collected, 'credit': Decimal('0')},
                {'account_code': pigmmy_head.code, 'debit': Decimal('0'), 'credit': total_collected},
            ],
            user=created_by,
            reference_type='pigmmy_collection',
        )

    return collection


def calculate_agent_commission(agent, month_start, month_end):
    total = PigmmyTransaction.objects.filter(
        collected_by=agent,
        txn_date__gte=month_start,
        txn_date__lte=month_end,
        is_reversed=False,
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

    commission = total * agent.commission_rate / 100

    tds = Decimal('0.00')
    yearly_commission = commission * 12
    if yearly_commission > Decimal('15000'):
        tds = commission * Decimal('0.10')

    return {
        'total_collection': total,
        'commission_rate': agent.commission_rate,
        'commission_amount': commission,
        'tds_amount': tds,
        'net_amount': commission - tds,
    }
