from datetime import date
from decimal import Decimal

from django.db import IntegrityError

from apps.agents.models import (
    Agent,
    AgentCollection,
    AgentCommission,
    PigmmyAccount,
    PigmmyTransaction,
)
from apps.agents.services import (
    calculate_agent_commission,
    create_pigmmy_account,
    record_agent_collection,
)
from apps.savings.models import SavingsAccount

from .base import BaseTestCase


class AgentModelTests(BaseTestCase):
    """Tests for Agent model creation and fields."""

    def setUp(self):
        super().setUp()
        self.savings_account = SavingsAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            account_no='SA-AG-001',
            account_type='savings',
            opening_date=date(2024, 1, 1),
            status='active',
            current_balance=Decimal('5000.00'),
        )

    def test_create_agent(self):
        agent = Agent.objects.create(
            agent_code='AG001',
            member=self.member1,
            branch=self.head_office,
            savings_account=self.savings_account,
            security_deposit_amount=Decimal('10000.00'),
            commission_rate=Decimal('2.00'),
            joining_date=date(2024, 1, 1),
            phone='9876543210',
            area='Pune Central',
            status='active',
            created_by=self.admin_user,
        )
        self.assertEqual(agent.agent_code, 'AG001')
        self.assertEqual(agent.member, self.member1)
        self.assertEqual(agent.commission_rate, Decimal('2.00'))
        self.assertEqual(str(agent), 'AG001 - Rajesh Kumar')

    def test_agent_code_unique(self):
        Agent.objects.create(
            agent_code='AG001',
            member=self.member1,
            branch=self.head_office,
            savings_account=self.savings_account,
            joining_date=date(2024, 1, 1),
            phone='9876543210',
            created_by=self.admin_user,
        )
        sa2 = SavingsAccount.objects.create(
            member=self.member2,
            branch=self.head_office,
            account_no='SA-AG-002',
            account_type='savings',
            opening_date=date(2024, 1, 1),
            status='active',
        )
        with self.assertRaises(IntegrityError):
            Agent.objects.create(
                agent_code='AG001',
                member=self.member2,
                branch=self.head_office,
                savings_account=sa2,
                joining_date=date(2024, 1, 1),
                phone='9876543211',
                created_by=self.admin_user,
            )

    def test_agent_status_transitions(self):
        agent = Agent.objects.create(
            agent_code='AG002',
            member=self.member1,
            branch=self.head_office,
            savings_account=self.savings_account,
            joining_date=date(2024, 1, 1),
            phone='9876543210',
            created_by=self.admin_user,
            status='active',
        )
        agent.status = 'inactive'
        agent.save()
        agent.refresh_from_db()
        self.assertEqual(agent.status, 'inactive')

        agent.status = 'terminated'
        agent.save()
        agent.refresh_from_db()
        self.assertEqual(agent.status, 'terminated')


class PigmmyAccountModelTests(BaseTestCase):
    """Tests for PigmmyAccount model."""

    def setUp(self):
        super().setUp()
        self.savings_account = SavingsAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            account_no='SA-PG-001',
            account_type='savings',
            opening_date=date(2024, 1, 1),
            status='active',
        )
        self.agent = Agent.objects.create(
            agent_code='AG010',
            member=self.member1,
            branch=self.head_office,
            savings_account=self.savings_account,
            joining_date=date(2024, 1, 1),
            phone='9876543210',
            created_by=self.admin_user,
        )

    def test_create_pigmmy_account(self):
        pa = PigmmyAccount.objects.create(
            account_no='PG000001',
            member=self.member2,
            branch=self.head_office,
            agent=self.agent,
            deposit_type='daily',
            installment_amount=Decimal('100.00'),
            deposit_period_months=12,
            interest_rate=Decimal('5.00'),
            opening_date=date(2024, 1, 1),
            maturity_date=date(2025, 1, 1),
            maturity_amount=Decimal('32000.00'),
            total_installments=312,
            status='active',
            created_by=self.admin_user,
        )
        self.assertEqual(pa.account_no, 'PG000001')
        self.assertEqual(pa.deposit_type, 'daily')
        self.assertEqual(pa.agent, self.agent)

    def test_pigmmy_account_no_unique(self):
        PigmmyAccount.objects.create(
            account_no='PG000001',
            member=self.member2,
            branch=self.head_office,
            agent=self.agent,
            installment_amount=Decimal('100.00'),
            deposit_period_months=12,
            interest_rate=Decimal('5.00'),
            opening_date=date(2024, 1, 1),
            maturity_date=date(2025, 1, 1),
            total_installments=312,
            created_by=self.admin_user,
        )
        with self.assertRaises(IntegrityError):
            PigmmyAccount.objects.create(
                account_no='PG000001',
                member=self.member3,
                branch=self.head_office,
                agent=self.agent,
                installment_amount=Decimal('50.00'),
                deposit_period_months=6,
                interest_rate=Decimal('4.00'),
                opening_date=date(2024, 1, 1),
                maturity_date=date(2024, 7, 1),
                total_installments=156,
                created_by=self.admin_user,
            )


class PigmmyTransactionTests(BaseTestCase):
    """Tests for PigmmyTransaction model."""

    def setUp(self):
        super().setUp()
        self.savings_account = SavingsAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            account_no='SA-PT-001',
            account_type='savings',
            opening_date=date(2024, 1, 1),
            status='active',
        )
        self.agent = Agent.objects.create(
            agent_code='AG020',
            member=self.member1,
            branch=self.head_office,
            savings_account=self.savings_account,
            joining_date=date(2024, 1, 1),
            phone='9876543210',
            created_by=self.admin_user,
        )
        self.pigmmy = PigmmyAccount.objects.create(
            account_no='PG000010',
            member=self.member2,
            branch=self.head_office,
            agent=self.agent,
            installment_amount=Decimal('100.00'),
            deposit_period_months=12,
            interest_rate=Decimal('5.00'),
            opening_date=date(2024, 1, 1),
            maturity_date=date(2025, 1, 1),
            total_installments=312,
            created_by=self.admin_user,
        )

    def test_create_transaction(self):
        txn = PigmmyTransaction.objects.create(
            account=self.pigmmy,
            branch=self.head_office,
            txn_date=date(2024, 1, 2),
            amount=Decimal('100.00'),
            running_balance=Decimal('100.00'),
            installment_no=1,
            narration='Daily collection',
            collected_by=self.agent,
            created_by=self.admin_user,
        )
        self.assertEqual(txn.amount, Decimal('100.00'))
        self.assertEqual(txn.running_balance, Decimal('100.00'))
        self.assertFalse(txn.is_reversed)


class AgentCollectionModelTests(BaseTestCase):
    """Tests for AgentCollection model."""

    def setUp(self):
        super().setUp()
        self.savings_account = SavingsAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            account_no='SA-AC-001',
            account_type='savings',
            opening_date=date(2024, 1, 1),
            status='active',
        )
        self.agent = Agent.objects.create(
            agent_code='AG030',
            member=self.member1,
            branch=self.head_office,
            savings_account=self.savings_account,
            joining_date=date(2024, 1, 1),
            phone='9876543210',
            created_by=self.admin_user,
        )

    def test_create_collection(self):
        coll = AgentCollection.objects.create(
            agent=self.agent,
            branch=self.head_office,
            collection_date=date(2024, 1, 2),
            total_clients_visited=10,
            total_clients_collected=8,
            expected_amount=Decimal('1000.00'),
            collected_amount=Decimal('800.00'),
            deposited_amount=Decimal('800.00'),
            status='submitted',
        )
        self.assertEqual(coll.collected_amount, Decimal('800.00'))
        self.assertEqual(coll.status, 'submitted')

    def test_collection_unique_per_agent_date(self):
        AgentCollection.objects.create(
            agent=self.agent,
            branch=self.head_office,
            collection_date=date(2024, 1, 2),
            status='open',
        )
        with self.assertRaises(IntegrityError):
            AgentCollection.objects.create(
                agent=self.agent,
                branch=self.head_office,
                collection_date=date(2024, 1, 2),
                status='open',
            )


class AgentCommissionModelTests(BaseTestCase):
    """Tests for AgentCommission model."""

    def setUp(self):
        super().setUp()
        self.savings_account = SavingsAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            account_no='SA-CM-001',
            account_type='savings',
            opening_date=date(2024, 1, 1),
            status='active',
        )
        self.agent = Agent.objects.create(
            agent_code='AG040',
            member=self.member1,
            branch=self.head_office,
            savings_account=self.savings_account,
            commission_rate=Decimal('2.00'),
            joining_date=date(2024, 1, 1),
            phone='9876543210',
            created_by=self.admin_user,
        )

    def test_create_commission(self):
        comm = AgentCommission.objects.create(
            agent=self.agent,
            month=date(2024, 1, 1),
            total_collection=Decimal('50000.00'),
            commission_rate=Decimal('2.00'),
            commission_amount=Decimal('1000.00'),
            tds_amount=Decimal('0.00'),
            net_amount=Decimal('1000.00'),
        )
        self.assertEqual(comm.commission_amount, Decimal('1000.00'))
        self.assertFalse(comm.paid)

    def test_commission_unique_per_agent_month(self):
        AgentCommission.objects.create(
            agent=self.agent,
            month=date(2024, 1, 1),
            total_collection=Decimal('50000.00'),
            commission_rate=Decimal('2.00'),
            commission_amount=Decimal('1000.00'),
            net_amount=Decimal('1000.00'),
        )
        with self.assertRaises(IntegrityError):
            AgentCommission.objects.create(
                agent=self.agent,
                month=date(2024, 1, 1),
                total_collection=Decimal('30000.00'),
                commission_rate=Decimal('2.00'),
                commission_amount=Decimal('600.00'),
                net_amount=Decimal('600.00'),
            )


class CreatePigmmyAccountServiceTests(BaseTestCase):
    """Tests for create_pigmmy_account service."""

    def setUp(self):
        super().setUp()
        self.savings_account = SavingsAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            account_no='SA-SVC-001',
            account_type='savings',
            opening_date=date(2024, 1, 1),
            status='active',
        )
        self.security_account = SavingsAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            account_no='SA-SEC-001',
            account_type='security',
            opening_date=date(2024, 1, 1),
            status='active',
        )
        self.agent = Agent.objects.create(
            agent_code='AG050',
            member=self.member1,
            branch=self.head_office,
            savings_account=self.savings_account,
            security_deposit_account=self.security_account,
            joining_date=date(2024, 1, 1),
            phone='9876543210',
            created_by=self.admin_user,
        )

    def test_create_daily_pigmmy(self):
        account = create_pigmmy_account(
            member=self.member2,
            agent=self.agent,
            branch=self.head_office,
            installment_amount=Decimal('100.00'),
            deposit_period_months=12,
            interest_rate=Decimal('5.00'),
            deposit_type='daily',
            created_by=self.admin_user,
        )
        self.assertTrue(len(account.account_no) > 0)
        self.assertEqual(account.deposit_type, 'daily')
        self.assertEqual(account.total_installments, 12 * 26)
        self.assertGreater(account.maturity_amount, Decimal('0'))

    def test_create_weekly_pigmmy(self):
        account = create_pigmmy_account(
            member=self.member2,
            agent=self.agent,
            branch=self.head_office,
            installment_amount=Decimal('500.00'),
            deposit_period_months=6,
            interest_rate=Decimal('4.00'),
            deposit_type='weekly',
            created_by=self.admin_user,
        )
        self.assertEqual(account.total_installments, 6 * 4)

    def test_create_monthly_pigmmy(self):
        account = create_pigmmy_account(
            member=self.member2,
            agent=self.agent,
            branch=self.head_office,
            installment_amount=Decimal('1000.00'),
            deposit_period_months=12,
            interest_rate=Decimal('6.00'),
            deposit_type='monthly',
            created_by=self.admin_user,
        )
        self.assertEqual(account.total_installments, 12)

    def test_auto_generated_account_no(self):
        a1 = create_pigmmy_account(
            member=self.member2,
            agent=self.agent,
            branch=self.head_office,
            installment_amount=Decimal('100.00'),
            deposit_period_months=6,
            interest_rate=Decimal('5.00'),
            created_by=self.admin_user,
        )
        a2 = create_pigmmy_account(
            member=self.member3,
            agent=self.agent,
            branch=self.head_office,
            installment_amount=Decimal('200.00'),
            deposit_period_months=6,
            interest_rate=Decimal('5.00'),
            created_by=self.admin_user,
        )
        self.assertNotEqual(a1.account_no, a2.account_no)


class RecordAgentCollectionServiceTests(BaseTestCase):
    """Tests for record_agent_collection service."""

    def setUp(self):
        super().setUp()
        from apps.accounting.models import ChartOfAccounts

        ChartOfAccounts.objects.create(
            code='1001',
            name='Cash in Hand',
            account_group='asset',
            account_type='cash',
            is_system=True,
        )
        ChartOfAccounts.objects.create(
            code='2050',
            name='Pigmmy Deposits',
            account_group='liability',
            account_type='deposits_taken',
            is_system=True,
        )

        self.savings_account = SavingsAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            account_no='SA-RC-001',
            account_type='savings',
            opening_date=date(2024, 1, 1),
            status='active',
        )
        self.agent = Agent.objects.create(
            agent_code='AG060',
            member=self.member1,
            branch=self.head_office,
            savings_account=self.savings_account,
            commission_rate=Decimal('2.00'),
            joining_date=date(2024, 1, 1),
            phone='9876543210',
            created_by=self.admin_user,
        )
        self.pigmmy1 = PigmmyAccount.objects.create(
            account_no='PG000020',
            member=self.member2,
            branch=self.head_office,
            agent=self.agent,
            installment_amount=Decimal('100.00'),
            deposit_period_months=12,
            interest_rate=Decimal('5.00'),
            opening_date=date(2024, 1, 1),
            maturity_date=date(2025, 1, 1),
            total_installments=312,
            created_by=self.admin_user,
        )
        self.pigmmy2 = PigmmyAccount.objects.create(
            account_no='PG000021',
            member=self.member3,
            branch=self.head_office,
            agent=self.agent,
            installment_amount=Decimal('200.00'),
            deposit_period_months=12,
            interest_rate=Decimal('5.00'),
            opening_date=date(2024, 1, 1),
            maturity_date=date(2025, 1, 1),
            total_installments=312,
            created_by=self.admin_user,
        )

    def test_record_collection(self):
        collection = record_agent_collection(
            agent=self.agent,
            collection_date=date(2024, 1, 2),
            client_payments=[
                {'account_id': self.pigmmy1.pk, 'amount': Decimal('100.00')},
                {'account_id': self.pigmmy2.pk, 'amount': Decimal('200.00')},
            ],
            branch=self.head_office,
            created_by=self.admin_user,
        )
        self.assertEqual(collection.collected_amount, Decimal('300.00'))
        self.assertEqual(collection.total_clients_collected, 2)
        self.assertEqual(collection.status, 'submitted')

    def test_collection_updates_pigmmy_balance(self):
        record_agent_collection(
            agent=self.agent,
            collection_date=date(2024, 1, 2),
            client_payments=[
                {'account_id': self.pigmmy1.pk, 'amount': Decimal('100.00')},
            ],
            branch=self.head_office,
            created_by=self.admin_user,
        )
        self.pigmmy1.refresh_from_db()
        self.assertEqual(self.pigmmy1.current_balance, Decimal('100.00'))
        self.assertEqual(self.pigmmy1.total_deposited, Decimal('100.00'))
        self.assertEqual(self.pigmmy1.paid_installments, 1)

    def test_collection_creates_transactions(self):
        record_agent_collection(
            agent=self.agent,
            collection_date=date(2024, 1, 2),
            client_payments=[
                {'account_id': self.pigmmy1.pk, 'amount': Decimal('100.00')},
            ],
            branch=self.head_office,
            created_by=self.admin_user,
        )
        txns = PigmmyTransaction.objects.filter(account=self.pigmmy1)
        self.assertEqual(txns.count(), 1)
        self.assertEqual(txns.first().amount, Decimal('100.00'))

    def test_zero_amount_skipped(self):
        collection = record_agent_collection(
            agent=self.agent,
            collection_date=date(2024, 1, 2),
            client_payments=[
                {'account_id': self.pigmmy1.pk, 'amount': Decimal('0.00')},
                {'account_id': self.pigmmy2.pk, 'amount': Decimal('200.00')},
            ],
            branch=self.head_office,
            created_by=self.admin_user,
        )
        self.assertEqual(collection.total_clients_collected, 1)
        self.assertEqual(collection.collected_amount, Decimal('200.00'))


class CalculateAgentCommissionTests(BaseTestCase):
    """Tests for calculate_agent_commission service."""

    def setUp(self):
        super().setUp()
        self.savings_account = SavingsAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            account_no='SA-CC-001',
            account_type='savings',
            opening_date=date(2024, 1, 1),
            status='active',
        )
        self.agent = Agent.objects.create(
            agent_code='AG070',
            member=self.member1,
            branch=self.head_office,
            savings_account=self.savings_account,
            commission_rate=Decimal('2.00'),
            joining_date=date(2024, 1, 1),
            phone='9876543210',
            created_by=self.admin_user,
        )
        self.pigmmy = PigmmyAccount.objects.create(
            account_no='PG000030',
            member=self.member2,
            branch=self.head_office,
            agent=self.agent,
            installment_amount=Decimal('100.00'),
            deposit_period_months=12,
            interest_rate=Decimal('5.00'),
            opening_date=date(2024, 1, 1),
            maturity_date=date(2025, 1, 1),
            total_installments=312,
            created_by=self.admin_user,
        )

    def test_commission_calculation(self):
        for day in range(1, 26):
            PigmmyTransaction.objects.create(
                account=self.pigmmy,
                branch=self.head_office,
                txn_date=date(2024, 1, day),
                amount=Decimal('100.00'),
                running_balance=Decimal('100.00') * day,
                collected_by=self.agent,
                created_by=self.admin_user,
            )
        result = calculate_agent_commission(
            self.agent,
            date(2024, 1, 1),
            date(2024, 1, 31),
        )
        self.assertEqual(result['total_collection'], Decimal('2500.00'))
        self.assertEqual(result['commission_rate'], Decimal('2.00'))
        self.assertEqual(result['commission_amount'], Decimal('50.00'))

    def test_commission_with_no_transactions(self):
        result = calculate_agent_commission(
            self.agent,
            date(2024, 1, 1),
            date(2024, 1, 31),
        )
        self.assertEqual(result['total_collection'], Decimal('0'))
        self.assertEqual(result['commission_amount'], Decimal('0'))

    def test_tds_on_high_commission(self):
        for day in range(1, 26):
            PigmmyTransaction.objects.create(
                account=self.pigmmy,
                branch=self.head_office,
                txn_date=date(2024, 1, day),
                amount=Decimal('5000.00'),
                running_balance=Decimal('5000.00') * day,
                collected_by=self.agent,
                created_by=self.admin_user,
            )
        result = calculate_agent_commission(
            self.agent,
            date(2024, 1, 1),
            date(2024, 1, 31),
        )
        self.assertGreater(result['tds_amount'], Decimal('0'))
        self.assertEqual(
            result['net_amount'],
            result['commission_amount'] - result['tds_amount'],
        )

    def test_reversed_transactions_excluded(self):
        PigmmyTransaction.objects.create(
            account=self.pigmmy,
            branch=self.head_office,
            txn_date=date(2024, 1, 1),
            amount=Decimal('100.00'),
            running_balance=Decimal('100.00'),
            collected_by=self.agent,
            created_by=self.admin_user,
            is_reversed=True,
        )
        result = calculate_agent_commission(
            self.agent,
            date(2024, 1, 1),
            date(2024, 1, 31),
        )
        self.assertEqual(result['total_collection'], Decimal('0'))
