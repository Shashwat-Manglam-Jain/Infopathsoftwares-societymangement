from decimal import Decimal

from apps.accounting.models import ChartOfAccounts, JournalEntry, JournalLine
from apps.shares.models import ShareConfig, ShareHolding, ShareTransaction
from apps.shares.services import (
    calculate_dividend,
    purchase_shares,
    surrender_shares,
    transfer_shares,
)

from .base import BaseTestCase


class ShareConfigTests(BaseTestCase):
    """Tests for share capital configuration."""

    def setUp(self):
        super().setUp()
        self.config = ShareConfig.objects.create(
            face_value_per_share=Decimal('100.00'),
            max_shares_per_member=100,
            min_shares_required=10,
            is_active=True,
        )

    def test_share_config_creation(self):
        """Share configuration stores face value and limits."""
        self.assertEqual(self.config.face_value_per_share, Decimal('100.00'))
        self.assertEqual(self.config.max_shares_per_member, 100)
        self.assertEqual(self.config.min_shares_required, 10)


class SharePurchaseTests(BaseTestCase):
    """Tests for share purchase operations."""

    def setUp(self):
        super().setUp()
        self.config = ShareConfig.objects.create(
            face_value_per_share=Decimal('100.00'),
            max_shares_per_member=100,
            min_shares_required=10,
            is_active=True,
        )
        self._setup_coa()

    def _setup_coa(self):
        """Create minimal chart of accounts for journal entries."""
        self.cash_account = ChartOfAccounts.objects.create(
            code='1001',
            name='Cash in Hand',
            account_group='asset',
            account_type='cash',
            is_system=True,
            branch=self.head_office,
        )
        self.share_capital_account = ChartOfAccounts.objects.create(
            code='2501',
            name='Share Capital',
            account_group='equity',
            account_type='share_capital',
            is_system=True,
        )

    def test_share_purchase(self):
        """Purchasing shares creates a holding and a transaction record."""
        holding = purchase_shares(
            member=self.member1,
            branch=self.head_office,
            count=20,
            user=self.cashier_user,
        )
        self.assertEqual(holding.share_count, 20)
        self.assertEqual(holding.total_amount, Decimal('2000.00'))  # 20 × 100
        self.assertEqual(holding.status, 'active')
        self.assertIsNotNone(holding.certificate_no)

        txn = ShareTransaction.objects.filter(member=self.member1, txn_type='purchase').first()
        self.assertIsNotNone(txn)
        self.assertEqual(txn.shares_count, 20)
        self.assertEqual(txn.amount, Decimal('2000.00'))

    def test_share_purchase_journal_entry(self):
        """Share purchase creates a balanced journal: DEBIT Cash, CREDIT Share Capital."""
        purchase_shares(
            member=self.member1,
            branch=self.head_office,
            count=10,
            user=self.cashier_user,
        )
        entry = JournalEntry.objects.filter(reference_type='share_purchase').first()
        self.assertIsNotNone(entry)

        lines = JournalLine.objects.filter(journal_entry=entry)
        total_debit = sum(l.debit_amount for l in lines)
        total_credit = sum(l.credit_amount for l in lines)
        self.assertEqual(total_debit, Decimal('1000.00'))
        self.assertEqual(total_credit, Decimal('1000.00'))

        debit_line = lines.filter(debit_amount__gt=0).first()
        credit_line = lines.filter(credit_amount__gt=0).first()
        self.assertEqual(debit_line.gl_account.account_type, 'cash')
        self.assertEqual(credit_line.gl_account.account_type, 'share_capital')

    def test_share_max_limit(self):
        """Cannot purchase more shares than max_shares_per_member."""
        with self.assertRaises(ValueError):
            purchase_shares(
                member=self.member1,
                branch=self.head_office,
                count=150,  # exceeds max of 100
                user=self.cashier_user,
            )

    def test_share_certificate_number_unique(self):
        """Each share holding gets a unique certificate number."""
        h1 = purchase_shares(
            member=self.member1,
            branch=self.head_office,
            count=10,
            user=self.cashier_user,
        )
        h2 = purchase_shares(
            member=self.member2,
            branch=self.branch_a,
            count=10,
            user=self.branch_cashier,
        )
        self.assertNotEqual(h1.certificate_no, h2.certificate_no)


class ShareTransferTests(BaseTestCase):
    """Tests for share transfer between members."""

    def setUp(self):
        super().setUp()
        self.config = ShareConfig.objects.create(
            face_value_per_share=Decimal('100.00'),
            max_shares_per_member=100,
            min_shares_required=10,
            is_active=True,
        )
        self._setup_coa()
        self.holding = purchase_shares(
            member=self.member1,
            branch=self.head_office,
            count=50,
            user=self.cashier_user,
        )

    def _setup_coa(self):
        ChartOfAccounts.objects.create(
            code='1001',
            name='Cash in Hand',
            account_group='asset',
            account_type='cash',
            is_system=True,
            branch=self.head_office,
        )
        ChartOfAccounts.objects.create(
            code='2501',
            name='Share Capital',
            account_group='equity',
            account_type='share_capital',
            is_system=True,
        )

    def test_share_transfer(self):
        """Transferring shares moves them from one member to another."""
        transfer_shares(
            from_member=self.member1,
            to_member=self.member2,
            count=20,
            user=self.admin_user,
        )
        from_holdings = ShareHolding.objects.filter(member=self.member1, status='active')
        to_holdings = ShareHolding.objects.filter(member=self.member2, status='active')
        from_total = sum(h.share_count for h in from_holdings)
        to_total = sum(h.share_count for h in to_holdings)
        self.assertEqual(from_total, 30)
        self.assertEqual(to_total, 20)

    def test_transfer_creates_transactions(self):
        """Transfer creates transaction records for both members."""
        transfer_shares(
            from_member=self.member1,
            to_member=self.member2,
            count=10,
            user=self.admin_user,
        )
        from_txn = ShareTransaction.objects.filter(member=self.member1, txn_type='transfer')
        to_txn = ShareTransaction.objects.filter(member=self.member2, txn_type='purchase')
        self.assertTrue(from_txn.exists())
        self.assertTrue(to_txn.exists())

    def test_cannot_transfer_more_than_held(self):
        """Cannot transfer more shares than the member holds."""
        with self.assertRaises(ValueError):
            transfer_shares(
                from_member=self.member1,
                to_member=self.member2,
                count=100,
                user=self.admin_user,
            )


class ShareSurrenderTests(BaseTestCase):
    """Tests for share surrender (buy-back)."""

    def setUp(self):
        super().setUp()
        self.config = ShareConfig.objects.create(
            face_value_per_share=Decimal('100.00'),
            max_shares_per_member=100,
            min_shares_required=10,
            is_active=True,
        )
        self._setup_coa()
        purchase_shares(
            member=self.member1,
            branch=self.head_office,
            count=50,
            user=self.cashier_user,
        )

    def _setup_coa(self):
        ChartOfAccounts.objects.create(
            code='1001',
            name='Cash in Hand',
            account_group='asset',
            account_type='cash',
            is_system=True,
            branch=self.head_office,
        )
        ChartOfAccounts.objects.create(
            code='2501',
            name='Share Capital',
            account_group='equity',
            account_type='share_capital',
            is_system=True,
        )

    def test_share_surrender(self):
        """Surrendering shares reduces holding and creates refund journal."""
        surrender_shares(
            member=self.member1,
            count=20,
            user=self.admin_user,
        )
        active = ShareHolding.objects.filter(member=self.member1, status='active')
        total = sum(h.share_count for h in active)
        self.assertEqual(total, 30)

        txn = ShareTransaction.objects.filter(member=self.member1, txn_type='surrender').first()
        self.assertIsNotNone(txn)
        self.assertEqual(txn.amount, Decimal('2000.00'))

    def test_surrender_cannot_exceed_holding(self):
        """Cannot surrender more shares than currently held."""
        with self.assertRaises(ValueError):
            surrender_shares(
                member=self.member1,
                count=60,  # only holds 50
                user=self.admin_user,
            )


class DividendTests(BaseTestCase):
    """Tests for dividend calculation and distribution."""

    def setUp(self):
        super().setUp()
        self.config = ShareConfig.objects.create(
            face_value_per_share=Decimal('100.00'),
            max_shares_per_member=100,
            min_shares_required=10,
            dividend_rate=Decimal('10.00'),
            is_active=True,
        )
        self._setup_coa()
        purchase_shares(
            member=self.member1,
            branch=self.head_office,
            count=50,
            user=self.cashier_user,
        )
        purchase_shares(
            member=self.member2,
            branch=self.branch_a,
            count=30,
            user=self.branch_cashier,
        )

    def _setup_coa(self):
        ChartOfAccounts.objects.create(
            code='1001',
            name='Cash in Hand',
            account_group='asset',
            account_type='cash',
            is_system=True,
            branch=self.head_office,
        )
        ChartOfAccounts.objects.create(
            code='2501',
            name='Share Capital',
            account_group='equity',
            account_type='share_capital',
            is_system=True,
        )

    def test_dividend_calculation(self):
        """Dividend at 10% on share capital is correctly calculated per member."""
        dividends = calculate_dividend(
            rate=Decimal('10.00'),
            financial_year='2024-25',
        )
        # member1: 50 shares × ₹100 × 10% = ₹500
        # member2: 30 shares × ₹100 × 10% = ₹300
        m1_div = next(d for d in dividends if d['member'] == self.member1)
        m2_div = next(d for d in dividends if d['member'] == self.member2)
        self.assertEqual(m1_div['dividend'], Decimal('500.00'))
        self.assertEqual(m2_div['dividend'], Decimal('300.00'))
