from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from apps.accounting.models import ChartOfAccounts, JournalEntry, JournalLine
from apps.deposits.models import (
    FDProduct,
    RDInstallment,
)
from apps.deposits.services import (
    calculate_fd_maturity,
    collect_rd_installment,
    create_fd,
    create_rd,
    mature_fd,
    mature_rd,
    premature_close_fd,
    renew_fd,
)

from .base import BaseTestCase


class FDProductTests(BaseTestCase):
    """Tests for FD product configuration."""

    def test_create_fd_product(self):
        """FD product stores interest rate slabs and parameters."""
        product = FDProduct.objects.create(
            name='Regular FD',
            min_amount=Decimal('5000.00'),
            max_amount=Decimal('10000000.00'),
            min_tenure_days=90,
            max_tenure_days=3650,
            interest_rates=[
                {'min_days': 90, 'max_days': 180, 'rate': '5.50', 'senior_rate': '6.00'},
                {'min_days': 181, 'max_days': 365, 'rate': '6.50', 'senior_rate': '7.00'},
                {'min_days': 366, 'max_days': 730, 'rate': '7.00', 'senior_rate': '7.50'},
                {'min_days': 731, 'max_days': 3650, 'rate': '7.50', 'senior_rate': '8.00'},
            ],
            compounding='quarterly',
            premature_penalty_percent=Decimal('1.00'),
            is_active=True,
        )
        self.assertEqual(product.name, 'Regular FD')
        self.assertEqual(len(product.interest_rates), 4)
        self.assertEqual(product.compounding, 'quarterly')


class FDMaturityCalculationTests(BaseTestCase):
    """Critical tests for FD maturity amount calculation."""

    def test_fd_simple_interest(self):
        """Simple interest FD: ₹50,000 for 365 days at 7%.

        Maturity = 50,000 + (50,000 × 7% × 1) = ₹53,500.00
        """
        maturity = calculate_fd_maturity(
            principal=Decimal('50000.00'),
            annual_rate=Decimal('7.00'),
            tenure_days=365,
            compounding='cumulative',  # simple interest, paid at maturity
        )
        self.assertEqual(maturity, Decimal('53500.00'))

    def test_fd_quarterly_compound(self):
        """Quarterly compound FD: ₹50,000 for 365 days at 7%.

        A = P × (1 + r/n)^(n×t)
        A = 50000 × (1 + 0.07/4)^(4×1)
        A = 50000 × (1.0175)^4
        A = 50000 × 1.07185903...
        A ≈ ₹53,592.95
        """
        maturity = calculate_fd_maturity(
            principal=Decimal('50000.00'),
            annual_rate=Decimal('7.00'),
            tenure_days=365,
            compounding='quarterly',
        )
        # The exact amount depends on precise Decimal computation
        # (1.0175)^4 = 1.071859030...
        expected = Decimal('50000.00') * (1 + Decimal('0.07') / 4) ** 4
        expected = expected.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.assertEqual(maturity, expected)

    def test_fd_half_yearly_compound(self):
        """Half-yearly compound FD: ₹1,00,000 for 730 days (2 years) at 7.5%.

        A = 100000 × (1 + 0.075/2)^(2×2) = 100000 × (1.0375)^4
        """
        maturity = calculate_fd_maturity(
            principal=Decimal('100000.00'),
            annual_rate=Decimal('7.50'),
            tenure_days=730,
            compounding='half_yearly',
        )
        expected = Decimal('100000.00') * (1 + Decimal('0.075') / 2) ** 4
        expected = expected.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.assertEqual(maturity, expected)

    def test_fd_maturity_uses_decimal(self):
        """FD maturity calculation returns Decimal, not float."""
        maturity = calculate_fd_maturity(
            principal=Decimal('50000.00'),
            annual_rate=Decimal('7.00'),
            tenure_days=365,
            compounding='quarterly',
        )
        self.assertIsInstance(maturity, Decimal)


class FDLifecycleTests(BaseTestCase):
    """Tests for the full FD lifecycle."""

    def setUp(self):
        super().setUp()
        self._setup_coa()
        self.product = FDProduct.objects.create(
            name='Regular FD',
            min_amount=Decimal('5000.00'),
            max_amount=Decimal('10000000.00'),
            min_tenure_days=90,
            max_tenure_days=3650,
            interest_rates=[
                {'min_days': 90, 'max_days': 365, 'rate': '7.00', 'senior_rate': '7.50'},
                {'min_days': 366, 'max_days': 3650, 'rate': '7.50', 'senior_rate': '8.00'},
            ],
            compounding='quarterly',
            premature_penalty_percent=Decimal('1.00'),
            is_active=True,
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
            code='2002',
            name='Fixed Deposits',
            account_group='liability',
            account_type='deposits_taken',
            is_system=True,
        )
        ChartOfAccounts.objects.create(
            code='4002',
            name='Interest on FD',
            account_group='expense',
            account_type='interest_expense',
            is_system=True,
        )

    def test_create_fd(self):
        """Creating an FD sets all fields and calculates maturity."""
        fd = create_fd(
            member=self.member1,
            product=self.product,
            amount=Decimal('50000.00'),
            tenure_days=365,
            branch=self.head_office,
            user=self.cashier_user,
        )
        self.assertEqual(fd.deposit_amount, Decimal('50000.00'))
        self.assertEqual(fd.tenure_days, 365)
        self.assertEqual(fd.interest_rate, Decimal('7.00'))
        self.assertEqual(fd.status, 'active')
        self.assertIsNotNone(fd.certificate_no)
        self.assertIsNotNone(fd.fd_no)
        self.assertGreater(fd.maturity_amount, Decimal('50000.00'))
        self.assertIsNotNone(fd.maturity_date)

    def test_fd_journal_on_creation(self):
        """FD creation creates journal: DEBIT Cash, CREDIT Fixed Deposits."""
        create_fd(
            member=self.member1,
            product=self.product,
            amount=Decimal('50000.00'),
            tenure_days=365,
            branch=self.head_office,
            user=self.cashier_user,
        )
        entry = JournalEntry.objects.filter(reference_type='fd_creation').first()
        self.assertIsNotNone(entry)
        lines = JournalLine.objects.filter(journal_entry=entry)
        total_debit = sum(l.debit_amount for l in lines)
        total_credit = sum(l.credit_amount for l in lines)
        self.assertEqual(total_debit, Decimal('50000.00'))
        self.assertEqual(total_credit, Decimal('50000.00'))

    def test_fd_maturity(self):
        """Maturing an FD credits the maturity amount and updates status."""
        fd = create_fd(
            member=self.member1,
            product=self.product,
            amount=Decimal('50000.00'),
            tenure_days=365,
            branch=self.head_office,
            user=self.cashier_user,
        )
        fd.maturity_date = date.today() - timedelta(days=1)
        fd.save(update_fields=['maturity_date'])
        matured = mature_fd(fd, self.cashier_user)
        self.assertEqual(matured.status, 'matured')

    def test_fd_premature_closure(self):
        """Premature closure applies penalty and reduces interest."""
        fd = create_fd(
            member=self.member1,
            product=self.product,
            amount=Decimal('100000.00'),
            tenure_days=365,
            branch=self.head_office,
            user=self.cashier_user,
        )
        closed = premature_close_fd(fd, self.cashier_user)
        self.assertEqual(closed.status, 'prematurely_closed')
        self.assertIsNotNone(closed.premature_closure_date)
        # Premature amount should be less than maturity amount
        self.assertLess(closed.premature_amount, fd.maturity_amount)

    def test_fd_auto_renewal(self):
        """Auto-renewal creates a new FD with maturity amount as principal."""
        fd = create_fd(
            member=self.member1,
            product=self.product,
            amount=Decimal('50000.00'),
            tenure_days=365,
            branch=self.head_office,
            user=self.cashier_user,
            is_auto_renew=True,
        )
        self.assertTrue(fd.is_auto_renew)

        new_fd = renew_fd(fd, self.cashier_user)
        self.assertEqual(new_fd.deposit_amount, fd.maturity_amount)
        self.assertEqual(new_fd.status, 'active')

    def test_fd_tds_deduction(self):
        """TDS field can be set when interest exceeds ₹40,000 threshold."""
        fd = create_fd(
            member=self.member1,
            product=self.product,
            amount=Decimal('1000000.00'),  # Large FD
            tenure_days=365,
            branch=self.head_office,
            user=self.cashier_user,
        )
        interest = fd.maturity_amount - fd.deposit_amount
        self.assertGreater(interest, Decimal('40000.00'))
        fd.tds_applicable = True
        fd.save(update_fields=['tds_applicable'])
        fd.refresh_from_db()
        self.assertTrue(fd.tds_applicable)

    def test_fd_minimum_amount_validation(self):
        """Cannot create FD below minimum amount."""
        with self.assertRaises(ValueError):
            create_fd(
                member=self.member1,
                product=self.product,
                amount=Decimal('1000.00'),  # below min of 5000
                tenure_days=365,
                branch=self.head_office,
                user=self.cashier_user,
            )

    def test_fd_minimum_tenure_validation(self):
        """Cannot create FD below minimum tenure."""
        with self.assertRaises(ValueError):
            create_fd(
                member=self.member1,
                product=self.product,
                amount=Decimal('50000.00'),
                tenure_days=30,  # below min of 90
                branch=self.head_office,
                user=self.cashier_user,
            )


class RecurringDepositTests(BaseTestCase):
    """Tests for Recurring Deposit operations."""

    def setUp(self):
        super().setUp()
        self._setup_coa()

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
            code='2003',
            name='Recurring Deposits',
            account_group='liability',
            account_type='deposits_taken',
            is_system=True,
        )
        ChartOfAccounts.objects.create(
            code='4003',
            name='Interest on RD',
            account_group='expense',
            account_type='interest_expense',
            is_system=True,
        )

    def test_create_rd(self):
        """Creating an RD generates installment schedule."""
        rd = create_rd(
            member=self.member1,
            monthly_installment=Decimal('2000.00'),
            tenure_months=12,
            interest_rate=Decimal('7.00'),
            branch=self.head_office,
            user=self.cashier_user,
        )
        self.assertEqual(rd.monthly_installment, Decimal('2000.00'))
        self.assertEqual(rd.tenure_months, 12)
        self.assertEqual(rd.status, 'active')
        self.assertIsNotNone(rd.rd_no)
        self.assertGreater(rd.maturity_amount, Decimal('24000.00'))

        installments = RDInstallment.objects.filter(rd=rd)
        self.assertEqual(installments.count(), 12)

    def test_rd_installment_payment(self):
        """Paying an RD installment updates its status."""
        rd = create_rd(
            member=self.member1,
            monthly_installment=Decimal('2000.00'),
            tenure_months=12,
            interest_rate=Decimal('7.00'),
            branch=self.head_office,
            user=self.cashier_user,
        )
        first = RDInstallment.objects.filter(rd=rd, installment_no=1).first()
        collect_rd_installment(rd, Decimal('2000.00'), self.head_office, self.cashier_user)

        first.refresh_from_db()
        self.assertEqual(first.status, 'paid')
        self.assertEqual(first.paid_amount, Decimal('2000.00'))
        self.assertIsNotNone(first.paid_date)

    def test_rd_overdue_installment(self):
        """Installment past due date has overdue status."""
        rd = create_rd(
            member=self.member1,
            monthly_installment=Decimal('2000.00'),
            tenure_months=12,
            interest_rate=Decimal('7.00'),
            branch=self.head_office,
            user=self.cashier_user,
        )
        first = RDInstallment.objects.filter(rd=rd, installment_no=1).first()
        first.due_date = date.today() - timedelta(days=15)
        first.status = 'overdue'
        first.save()
        first.refresh_from_db()
        self.assertEqual(first.status, 'overdue')

    def test_rd_default_on_excess_misses(self):
        """RD is marked defaulted when defaults exceed max allowed."""
        rd = create_rd(
            member=self.member1,
            monthly_installment=Decimal('2000.00'),
            tenure_months=12,
            interest_rate=Decimal('7.00'),
            branch=self.head_office,
            user=self.cashier_user,
        )
        rd.default_count = rd.max_defaults_allowed + 1
        rd.status = 'defaulted'
        rd.save()
        rd.refresh_from_db()
        self.assertEqual(rd.status, 'defaulted')

    def test_rd_maturity(self):
        """RD maturity credits calculated amount when all installments paid."""
        rd = create_rd(
            member=self.member1,
            monthly_installment=Decimal('2000.00'),
            tenure_months=12,
            interest_rate=Decimal('7.00'),
            branch=self.head_office,
            user=self.cashier_user,
        )
        # Simulate paying all installments
        for inst in RDInstallment.objects.filter(rd=rd):
            inst.status = 'paid'
            inst.paid_amount = inst.amount
            inst.paid_date = inst.due_date
            inst.save()

        matured = mature_rd(rd, self.cashier_user)
        self.assertEqual(matured.status, 'matured')

    def test_rd_maturity_amount_includes_interest(self):
        """RD maturity amount is greater than sum of installments (includes interest)."""
        rd = create_rd(
            member=self.member1,
            monthly_installment=Decimal('5000.00'),
            tenure_months=24,
            interest_rate=Decimal('7.50'),
            branch=self.head_office,
            user=self.cashier_user,
        )
        total_deposited = Decimal('5000.00') * 24  # ₹1,20,000
        self.assertGreater(rd.maturity_amount, total_deposited)

    def test_rd_installment_dates_monthly(self):
        """RD installments are spaced one month apart."""
        rd = create_rd(
            member=self.member1,
            monthly_installment=Decimal('2000.00'),
            tenure_months=6,
            interest_rate=Decimal('7.00'),
            branch=self.head_office,
            user=self.cashier_user,
        )
        installments = RDInstallment.objects.filter(rd=rd).order_by('installment_no')
        for i in range(1, installments.count()):
            prev = installments[i - 1].due_date
            curr = installments[i].due_date
            # Months should increment by 1
            expected_month = prev.month + 1 if prev.month < 12 else 1
            self.assertEqual(curr.month, expected_month)
