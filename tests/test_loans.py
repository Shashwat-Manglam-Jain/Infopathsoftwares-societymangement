from datetime import date, timedelta
from decimal import Decimal

from apps.accounting.models import ChartOfAccounts, JournalEntry, JournalLine
from apps.loans.models import (
    EMISchedule,
    LoanAccount,
    LoanCollateral,
    LoanGuarantor,
    LoanProduct,
    StandingInstruction,
)
from apps.loans.services import (
    add_standing_instruction,
    approve_loan,
    calculate_emi,
    close_loan,
    collect_emi,
    disburse_loan,
    generate_emi_schedule,
    get_active_guarantee_count,
    mark_npa,
    mark_overdue,
    prepay_loan,
    validate_loan_application,
)
from apps.shares.models import ShareHolding

from .base import BaseTestCase


class LoanProductTests(BaseTestCase):
    """Tests for loan product configuration."""

    def test_create_loan_product(self):
        """Loan product stores all parameters correctly."""
        product = LoanProduct.objects.create(
            name='Personal Loan',
            interest_rate=Decimal('12.00'),
            max_amount=Decimal('500000.00'),
            max_tenure_months=60,
            interest_type='reducing_monthly',
            requires_guarantor=True,
            max_guarantors=2,
            requires_collateral=False,
            processing_fee_percent=Decimal('1.00'),
            penal_interest_rate=Decimal('2.00'),
            npa_days_threshold=90,
            is_active=True,
        )
        self.assertEqual(product.name, 'Personal Loan')
        self.assertEqual(product.interest_rate, Decimal('12.00'))
        self.assertEqual(product.interest_type, 'reducing_monthly')
        self.assertTrue(product.requires_guarantor)


class EMICalculationTests(BaseTestCase):
    """Critical tests for EMI calculation accuracy."""

    def test_emi_calculation_flat(self):
        """Flat rate EMI: ₹1,00,000 at 12% flat for 12 months.

        Total interest = 1,00,000 × 12% × 1 year = ₹12,000
        EMI = (1,00,000 + 12,000) / 12 = ₹9,333.33
        """
        emi = calculate_emi(
            principal=Decimal('100000.00'),
            annual_rate=Decimal('12.00'),
            tenure_months=12,
            interest_type='flat',
        )
        self.assertEqual(emi, Decimal('9333.33'))

    def test_emi_calculation_reducing(self):
        """Reducing balance EMI: ₹1,00,000 at 12% for 12 months.

        EMI = P × r × (1+r)^n / ((1+r)^n - 1)
        r = 12% / 12 = 1% = 0.01
        EMI = 100000 × 0.01 × 1.01^12 / (1.01^12 - 1)
        EMI = ₹8,884.88 (approximately)
        """
        emi = calculate_emi(
            principal=Decimal('100000.00'),
            annual_rate=Decimal('12.00'),
            tenure_months=12,
            interest_type='reducing_monthly',
        )
        self.assertEqual(emi, Decimal('8884.88'))

    def test_emi_calculation_uses_decimal(self):
        """EMI calculation returns a Decimal, not a float."""
        emi = calculate_emi(
            principal=Decimal('100000.00'),
            annual_rate=Decimal('12.00'),
            tenure_months=12,
            interest_type='reducing_monthly',
        )
        self.assertIsInstance(emi, Decimal)


class EMIScheduleTests(BaseTestCase):
    """Tests for EMI schedule generation with correct principal/interest split."""

    def setUp(self):
        super().setUp()
        self._setup_coa()
        self.product = LoanProduct.objects.create(
            name='Personal Loan',
            interest_rate=Decimal('12.00'),
            max_amount=Decimal('500000.00'),
            max_tenure_months=60,
            interest_type='reducing_monthly',
            requires_guarantor=False,
            processing_fee_percent=Decimal('0.00'),
            penal_interest_rate=Decimal('2.00'),
            npa_days_threshold=90,
            is_active=True,
        )
        self.loan = LoanAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            loan_product=self.product,
            loan_no='LN0001',
            applied_date=date(2024, 1, 1),
            applied_amount=Decimal('100000.00'),
            interest_rate=Decimal('12.00'),
            tenure_months=12,
            status='disbursed',
            approved_date=date(2024, 1, 5),
            approved_amount=Decimal('100000.00'),
            approved_by=self.manager_user,
            disbursed_amount=Decimal('100000.00'),
            disbursed_date=date(2024, 1, 10),
            outstanding_principal=Decimal('100000.00'),
            created_by=self.cashier_user,
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
            code='1003',
            name='Loans & Advances',
            account_group='asset',
            account_type='loans_given',
            is_system=True,
        )
        ChartOfAccounts.objects.create(
            code='3001',
            name='Interest on Loans',
            account_group='income',
            account_type='interest_income',
            is_system=True,
        )
        ChartOfAccounts.objects.create(
            code='3002',
            name='Processing Fees',
            account_group='income',
            account_type='other',
            is_system=True,
        )

    def test_emi_schedule_generation(self):
        """EMI schedule has correct number of installments."""
        schedule = generate_emi_schedule(self.loan)
        self.assertEqual(len(schedule), 12)

    def test_emi_schedule_principal_interest_split(self):
        """Each EMI correctly splits into principal and interest (reducing balance).

        Month 1: Interest = 1,00,000 × 12%/12 = ₹1,000.00
                 Principal = ₹8,884.88 - ₹1,000.00 = ₹7,884.88
        Month 2: Interest = (1,00,000 - 7,884.88) × 1% = ₹921.15
                 Principal = ₹8,884.88 - ₹921.15 = ₹7,963.73
        Month 3: Interest = (92,115.12 - 7,963.73) × 1% = ₹841.51
                 Principal = ₹8,884.88 - ₹841.51 = ₹8,043.37
        """
        schedule = generate_emi_schedule(self.loan)

        # Month 1
        self.assertEqual(schedule[0].interest_component, Decimal('1000.00'))
        self.assertEqual(schedule[0].principal_component, Decimal('7884.88'))
        self.assertEqual(schedule[0].total_emi, Decimal('8884.88'))

        # Month 2
        self.assertEqual(schedule[1].interest_component, Decimal('921.15'))
        self.assertEqual(schedule[1].principal_component, Decimal('7963.73'))

        # Month 3
        self.assertEqual(schedule[2].interest_component, Decimal('841.51'))
        self.assertEqual(schedule[2].principal_component, Decimal('8043.37'))

    def test_emi_schedule_total_equals_principal_plus_interest(self):
        """Sum of all principal components equals original principal.
        Sum of principal + interest across all EMIs = total repayment.
        """
        schedule = generate_emi_schedule(self.loan)
        total_principal = sum(e.principal_component for e in schedule)
        total_interest = sum(e.interest_component for e in schedule)

        # Total principal repaid should equal the loan amount
        self.assertEqual(
            total_principal.quantize(Decimal('1.00')),
            Decimal('100000.00'),
        )
        # Total interest should be positive
        self.assertGreater(total_interest, Decimal('0'))

    def test_emi_schedule_dates(self):
        """EMI due dates are spaced one month apart."""
        schedule = generate_emi_schedule(self.loan)
        for i in range(1, len(schedule)):
            prev_month = schedule[i - 1].due_date.month
            curr_month = schedule[i].due_date.month
            expected = prev_month + 1 if prev_month < 12 else 1
            self.assertEqual(curr_month, expected)


class LoanLifecycleTests(BaseTestCase):
    """Tests for the full loan lifecycle: apply → approve → disburse → repay → close."""

    def setUp(self):
        super().setUp()
        self._setup_coa()
        self.product = LoanProduct.objects.create(
            name='Personal Loan',
            interest_rate=Decimal('12.00'),
            max_amount=Decimal('500000.00'),
            max_tenure_months=60,
            interest_type='reducing_monthly',
            requires_guarantor=False,
            max_guarantors=2,
            processing_fee_percent=Decimal('1.00'),
            penal_interest_rate=Decimal('2.00'),
            npa_days_threshold=90,
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
            code='1003',
            name='Loans & Advances',
            account_group='asset',
            account_type='loans_given',
            is_system=True,
        )
        ChartOfAccounts.objects.create(
            code='3001',
            name='Interest on Loans',
            account_group='income',
            account_type='interest_income',
            is_system=True,
        )
        ChartOfAccounts.objects.create(
            code='3002',
            name='Processing Fees',
            account_group='income',
            account_type='other',
            is_system=True,
        )
        ChartOfAccounts.objects.create(
            code='3003',
            name='Penal Interest',
            account_group='income',
            account_type='other',
            is_system=True,
        )

    def _create_loan(self):
        return LoanAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            loan_product=self.product,
            loan_no='LN0001',
            applied_date=date(2024, 1, 1),
            applied_amount=Decimal('100000.00'),
            interest_rate=Decimal('12.00'),
            tenure_months=12,
            status='applied',
            created_by=self.cashier_user,
        )

    def test_loan_application(self):
        """Applying for a loan creates a record with status=applied."""
        loan = self._create_loan()
        self.assertEqual(loan.status, 'applied')
        self.assertEqual(loan.applied_amount, Decimal('100000.00'))

    def test_loan_approval(self):
        """Approving sets status, amount, approver, and date."""
        loan = self._create_loan()
        approve_loan(loan, Decimal('100000.00'), self.manager_user)
        loan.refresh_from_db()
        self.assertEqual(loan.status, 'approved')
        self.assertEqual(loan.approved_amount, Decimal('100000.00'))
        self.assertEqual(loan.approved_by, self.manager_user)
        self.assertIsNotNone(loan.approved_date)

    def test_loan_rejection(self):
        """Rejecting a loan sets status=rejected."""
        loan = self._create_loan()
        loan.status = 'rejected'
        loan.remarks = 'Insufficient collateral'
        loan.save()
        loan.refresh_from_db()
        self.assertEqual(loan.status, 'rejected')

    def test_loan_disbursement(self):
        """Disbursing sets outstanding principal, generates EMI schedule, creates journal."""
        loan = self._create_loan()
        approve_loan(loan, Decimal('100000.00'), self.manager_user)
        disburse_loan(loan, self.head_office, self.cashier_user)
        loan.refresh_from_db()

        self.assertEqual(loan.status, 'disbursed')
        self.assertEqual(loan.outstanding_principal, Decimal('100000.00'))
        self.assertIsNotNone(loan.disbursed_date)
        self.assertIsNotNone(loan.emi_amount)

        # EMI schedule generated
        emis = EMISchedule.objects.filter(loan=loan)
        self.assertEqual(emis.count(), 12)

    def test_loan_disbursement_journal(self):
        """Disbursement creates: DEBIT Loans & Advances, CREDIT Cash."""
        loan = self._create_loan()
        approve_loan(loan, Decimal('100000.00'), self.manager_user)
        disburse_loan(loan, self.head_office, self.cashier_user)

        entry = JournalEntry.objects.filter(reference_type='loan_disbursement').first()
        self.assertIsNotNone(entry)

        lines = JournalLine.objects.filter(journal_entry=entry)
        total_debit = sum(l.debit_amount for l in lines)
        total_credit = sum(l.credit_amount for l in lines)
        self.assertEqual(total_debit, total_credit)

    def test_emi_collection(self):
        """Collecting EMI splits payment into principal and interest."""
        loan = self._create_loan()
        approve_loan(loan, Decimal('100000.00'), self.manager_user)
        disburse_loan(loan, self.head_office, self.cashier_user)
        loan.refresh_from_db()

        emi_amount = loan.emi_amount
        repayment = collect_emi(
            loan=loan,
            amount=emi_amount,
            branch=self.head_office,
            user=self.cashier_user,
            payment_mode='cash',
        )
        loan.refresh_from_db()

        self.assertEqual(
            repayment.principal_adjusted + repayment.interest_adjusted,
            emi_amount,
        )
        self.assertLess(loan.outstanding_principal, Decimal('100000.00'))

        # First EMI marked as paid
        first_emi = EMISchedule.objects.filter(loan=loan, installment_no=1).first()
        self.assertEqual(first_emi.status, 'paid')

    def test_emi_collection_journal(self):
        """EMI collection creates: DEBIT Cash, CREDIT Loans & Advances + Interest Income."""
        loan = self._create_loan()
        approve_loan(loan, Decimal('100000.00'), self.manager_user)
        disburse_loan(loan, self.head_office, self.cashier_user)
        loan.refresh_from_db()

        collect_emi(loan, loan.emi_amount, self.head_office, self.cashier_user, 'cash')

        entry = JournalEntry.objects.filter(reference_type='emi_payment').first()
        self.assertIsNotNone(entry)
        lines = JournalLine.objects.filter(journal_entry=entry)
        total_debit = sum(l.debit_amount for l in lines)
        total_credit = sum(l.credit_amount for l in lines)
        self.assertEqual(total_debit, total_credit)

    def test_partial_emi_payment(self):
        """Partial payment marks EMI as partially_paid."""
        loan = self._create_loan()
        approve_loan(loan, Decimal('100000.00'), self.manager_user)
        disburse_loan(loan, self.head_office, self.cashier_user)
        loan.refresh_from_db()

        partial = loan.emi_amount / 2
        collect_emi(loan, partial, self.head_office, self.cashier_user, 'cash')

        first_emi = EMISchedule.objects.filter(loan=loan, installment_no=1).first()
        self.assertEqual(first_emi.status, 'partially_paid')
        self.assertEqual(first_emi.paid_amount, partial)

    def test_loan_prepayment(self):
        """Prepayment reduces outstanding principal beyond regular EMI."""
        loan = self._create_loan()
        approve_loan(loan, Decimal('100000.00'), self.manager_user)
        disburse_loan(loan, self.head_office, self.cashier_user)
        loan.refresh_from_db()

        # Pay first EMI
        collect_emi(loan, loan.emi_amount, self.head_office, self.cashier_user, 'cash')
        loan.refresh_from_db()
        balance_after_emi = loan.outstanding_principal

        # Prepay ₹20,000 extra
        prepay_loan(loan, Decimal('20000.00'), self.head_office, self.cashier_user)
        loan.refresh_from_db()
        self.assertEqual(
            loan.outstanding_principal,
            balance_after_emi - Decimal('20000.00'),
        )

    def test_loan_closure(self):
        """Closing a loan sets status=closed when outstanding is zero."""
        loan = self._create_loan()
        approve_loan(loan, Decimal('100000.00'), self.manager_user)
        disburse_loan(loan, self.head_office, self.cashier_user)
        loan.refresh_from_db()

        # Simulate paying off entire loan
        loan.outstanding_principal = Decimal('0.00')
        loan.outstanding_interest = Decimal('0.00')
        loan.overdue_amount = Decimal('0.00')
        loan.save()

        close_loan(loan, self.admin_user)
        loan.refresh_from_db()
        self.assertEqual(loan.status, 'closed')
        self.assertIsNotNone(loan.closure_date)
        self.assertEqual(loan.closure_type, 'normal')

    def test_cannot_close_with_outstanding(self):
        """Cannot close a loan that still has outstanding balance."""
        loan = self._create_loan()
        approve_loan(loan, Decimal('100000.00'), self.manager_user)
        disburse_loan(loan, self.head_office, self.cashier_user)

        with self.assertRaises(ValueError):
            close_loan(loan, self.admin_user)


class LoanOverdueNPATests(BaseTestCase):
    """Tests for overdue marking and NPA classification."""

    def setUp(self):
        super().setUp()
        self._setup_coa()
        self.product = LoanProduct.objects.create(
            name='Personal Loan',
            interest_rate=Decimal('12.00'),
            max_amount=Decimal('500000.00'),
            max_tenure_months=60,
            interest_type='reducing_monthly',
            requires_guarantor=False,
            penal_interest_rate=Decimal('2.00'),
            npa_days_threshold=90,
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
            code='1003',
            name='Loans & Advances',
            account_group='asset',
            account_type='loans_given',
            is_system=True,
        )
        ChartOfAccounts.objects.create(
            code='3001',
            name='Interest on Loans',
            account_group='income',
            account_type='interest_income',
            is_system=True,
        )
        ChartOfAccounts.objects.create(
            code='3002',
            name='Processing Fees',
            account_group='income',
            account_type='other',
            is_system=True,
        )
        ChartOfAccounts.objects.create(
            code='3003',
            name='Penal Interest',
            account_group='income',
            account_type='other',
            is_system=True,
        )

    def _create_disbursed_loan(self):
        loan = LoanAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            loan_product=self.product,
            loan_no='LN-OD-001',
            applied_date=date(2024, 1, 1),
            applied_amount=Decimal('100000.00'),
            interest_rate=Decimal('12.00'),
            tenure_months=12,
            status='applied',
            created_by=self.cashier_user,
        )
        approve_loan(loan, Decimal('100000.00'), self.manager_user)
        disburse_loan(loan, self.head_office, self.cashier_user)
        loan.refresh_from_db()
        return loan

    def test_overdue_marking(self):
        """EMIs past due date are marked overdue with correct days count."""
        loan = self._create_disbursed_loan()

        first_emi = EMISchedule.objects.filter(loan=loan, installment_no=1).first()
        # Set due date to 30 days ago
        first_emi.due_date = date.today() - timedelta(days=30)
        first_emi.save()

        mark_overdue(loan)
        loan.refresh_from_db()
        first_emi.refresh_from_db()

        self.assertEqual(first_emi.status, 'overdue')
        self.assertGreaterEqual(loan.overdue_days, 30)
        self.assertGreater(loan.overdue_amount, Decimal('0'))

    def test_npa_classification(self):
        """Loan overdue > 90 days is classified as NPA."""
        loan = self._create_disbursed_loan()
        loan.overdue_days = 95
        loan.overdue_amount = Decimal('10000.00')
        loan.save()

        mark_npa(loan)
        loan.refresh_from_db()
        self.assertEqual(loan.status, 'npa')

    def test_npa_not_marked_under_threshold(self):
        """Loan overdue < 90 days is NOT marked NPA."""
        loan = self._create_disbursed_loan()
        loan.overdue_days = 60
        loan.save()

        mark_npa(loan)
        loan.refresh_from_db()
        self.assertEqual(loan.status, 'disbursed')  # unchanged


class GuarantorCollateralTests(BaseTestCase):
    """Tests for loan guarantor and collateral management."""

    def setUp(self):
        super().setUp()
        self.product = LoanProduct.objects.create(
            name='Gold Loan',
            interest_rate=Decimal('10.00'),
            max_amount=Decimal('200000.00'),
            max_tenure_months=36,
            interest_type='reducing_monthly',
            requires_guarantor=True,
            max_guarantors=2,
            requires_collateral=True,
            is_active=True,
        )
        self.loan = LoanAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            loan_product=self.product,
            loan_no='LN-GC-001',
            applied_date=date(2024, 1, 1),
            applied_amount=Decimal('100000.00'),
            interest_rate=Decimal('10.00'),
            tenure_months=24,
            status='applied',
            created_by=self.cashier_user,
        )

    def test_guarantor_assignment(self):
        """Guarantors can be assigned to a loan."""
        g = LoanGuarantor.objects.create(
            loan=self.loan,
            guarantor_member=self.member2,
            guarantee_amount=Decimal('50000.00'),
        )
        self.assertEqual(g.guarantor_member, self.member2)
        self.assertEqual(g.guarantee_amount, Decimal('50000.00'))

    def test_multiple_guarantors(self):
        """Multiple guarantors can cover the loan amount."""
        LoanGuarantor.objects.create(
            loan=self.loan,
            guarantor_member=self.member2,
            guarantee_amount=Decimal('50000.00'),
        )
        LoanGuarantor.objects.create(
            loan=self.loan,
            guarantor_member=self.member3,
            guarantee_amount=Decimal('50000.00'),
        )
        guarantors = LoanGuarantor.objects.filter(loan=self.loan)
        total = sum(g.guarantee_amount for g in guarantors)
        self.assertEqual(total, Decimal('100000.00'))
        self.assertEqual(guarantors.count(), 2)

    def test_collateral_assignment(self):
        """Collateral can be assigned to a loan."""
        c = LoanCollateral.objects.create(
            loan=self.loan,
            collateral_type='gold',
            description='50g gold ornaments',
            estimated_value=Decimal('250000.00'),
            status='pledged',
        )
        self.assertEqual(c.collateral_type, 'gold')
        self.assertEqual(c.estimated_value, Decimal('250000.00'))
        self.assertEqual(c.status, 'pledged')

    def test_collateral_release_on_closure(self):
        """Collateral status can be updated to released."""
        c = LoanCollateral.objects.create(
            loan=self.loan,
            collateral_type='property',
            description='Plot no 123',
            estimated_value=Decimal('500000.00'),
            status='pledged',
        )
        c.status = 'released'
        c.save()
        c.refresh_from_db()
        self.assertEqual(c.status, 'released')


class LoanProductCategoryTests(BaseTestCase):
    """Tests for loan_category, mortgage_type, and new product flags."""

    def test_create_mortgage_product(self):
        product = LoanProduct.objects.create(
            name='Gold Loan (Mortgage)',
            interest_rate=Decimal('10.00'),
            max_amount=Decimal('200000.00'),
            max_tenure_months=36,
            interest_type='reducing_monthly',
            loan_category='mortgage',
            mortgage_type='gold',
            allow_multiple=True,
            requires_guarantor=False,
            guarantor_must_be_shareholder=False,
            requires_director_recommendation=False,
            is_active=True,
        )
        self.assertEqual(product.loan_category, 'mortgage')
        self.assertEqual(product.mortgage_type, 'gold')
        self.assertTrue(product.allow_multiple)

    def test_create_regular_product(self):
        product = LoanProduct.objects.create(
            name='Personal Loan',
            interest_rate=Decimal('12.00'),
            max_amount=Decimal('500000.00'),
            max_tenure_months=60,
            interest_type='reducing_monthly',
            loan_category='regular',
            mortgage_type='none',
            allow_multiple=False,
            requires_guarantor=True,
            guarantor_must_be_shareholder=True,
            requires_director_recommendation=True,
            is_active=True,
        )
        self.assertEqual(product.loan_category, 'regular')
        self.assertEqual(product.mortgage_type, 'none')
        self.assertFalse(product.allow_multiple)
        self.assertTrue(product.guarantor_must_be_shareholder)
        self.assertTrue(product.requires_director_recommendation)

    def test_mortgage_type_choices(self):
        for mt, _ in LoanProduct.MORTGAGE_TYPE_CHOICES:
            product = LoanProduct.objects.create(
                name=f'Product {mt}',
                interest_rate=Decimal('10.00'),
                max_amount=Decimal('100000.00'),
                max_tenure_months=12,
                loan_category='mortgage',
                mortgage_type=mt,
                is_active=True,
            )
            self.assertEqual(product.mortgage_type, mt)


class LoanAccountExtendedFieldsTests(BaseTestCase):
    """Tests for new LoanAccount fields: form_no, sanction, mortgage, notice, court_case."""

    def setUp(self):
        super().setUp()
        self.product = LoanProduct.objects.create(
            name='Mortgage Loan',
            interest_rate=Decimal('10.00'),
            max_amount=Decimal('500000.00'),
            max_tenure_months=60,
            interest_type='reducing_monthly',
            loan_category='mortgage',
            mortgage_type='fixed_deposit',
            is_active=True,
        )

    def test_extended_fields_persist(self):
        loan = LoanAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            loan_product=self.product,
            loan_no='LN-EXT-001',
            applied_date=date(2024, 1, 1),
            applied_amount=Decimal('100000.00'),
            interest_rate=Decimal('10.00'),
            tenure_months=24,
            status='applied',
            loan_form_no='LF-2024-001',
            sanction_date=date(2024, 1, 10),
            sanction_amount=Decimal('100000.00'),
            mortgage_account_no='FD001',
            mortgage_value=Decimal('120000.00'),
        )
        loan.refresh_from_db()
        self.assertEqual(loan.loan_form_no, 'LF-2024-001')
        self.assertEqual(loan.sanction_date, date(2024, 1, 10))
        self.assertEqual(loan.sanction_amount, Decimal('100000.00'))
        self.assertEqual(loan.mortgage_account_no, 'FD001')
        self.assertEqual(loan.mortgage_value, Decimal('120000.00'))

    def test_notice_and_court_case_fields(self):
        loan = LoanAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            loan_product=self.product,
            loan_no='LN-EXT-002',
            applied_date=date(2024, 1, 1),
            applied_amount=Decimal('50000.00'),
            interest_rate=Decimal('10.00'),
            tenure_months=12,
            status='disbursed',
            outstanding_principal=Decimal('50000.00'),
        )
        loan.notice_issued = True
        loan.notice_date = date(2024, 6, 1)
        loan.court_case = True
        loan.court_case_details = 'Case filed in district court'
        loan.save()
        loan.refresh_from_db()
        self.assertTrue(loan.notice_issued)
        self.assertEqual(loan.notice_date, date(2024, 6, 1))
        self.assertTrue(loan.court_case)
        self.assertEqual(loan.court_case_details, 'Case filed in district court')

    def test_director_recommendation(self):
        self.member3.is_director = True
        self.member3.save()
        loan = LoanAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            loan_product=self.product,
            loan_no='LN-EXT-003',
            applied_date=date(2024, 1, 1),
            applied_amount=Decimal('100000.00'),
            interest_rate=Decimal('10.00'),
            tenure_months=24,
            status='applied',
            director_recommendation=self.member3,
        )
        loan.refresh_from_db()
        self.assertEqual(loan.director_recommendation, self.member3)


class StandingInstructionTests(BaseTestCase):
    """Tests for StandingInstruction model and add_standing_instruction service."""

    def setUp(self):
        super().setUp()
        self._setup_coa()
        self.product = LoanProduct.objects.create(
            name='Personal Loan',
            interest_rate=Decimal('12.00'),
            max_amount=Decimal('500000.00'),
            max_tenure_months=60,
            interest_type='reducing_monthly',
            is_active=True,
        )
        self.loan = LoanAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            loan_product=self.product,
            loan_no='LN-SI-001',
            applied_date=date(2024, 1, 1),
            applied_amount=Decimal('100000.00'),
            interest_rate=Decimal('12.00'),
            tenure_months=12,
            status='disbursed',
            outstanding_principal=Decimal('100000.00'),
        )

    def _setup_coa(self):
        ChartOfAccounts.objects.create(
            code='1001',
            name='Cash',
            account_group='asset',
            account_type='cash',
            is_system=True,
            branch=self.head_office,
        )
        ChartOfAccounts.objects.create(
            code='1101',
            name='Loans & Advances',
            account_group='asset',
            account_type='loans_given',
            is_system=True,
        )
        ChartOfAccounts.objects.create(
            code='3002',
            name='Processing Fees',
            account_group='income',
            account_type='other',
            is_system=True,
        )
        ChartOfAccounts.objects.create(
            code='4004',
            name='Legal & Court Fees',
            account_group='income',
            account_type='other',
            is_system=True,
        )

    def test_create_standing_instruction(self):
        si = StandingInstruction.objects.create(
            loan=self.loan,
            branch=self.head_office,
            charge_type='form_fees',
            amount=Decimal('500.00'),
            charge_date=date(2024, 2, 1),
            narration='Loan form fees',
            created_by=self.cashier_user,
        )
        self.assertEqual(si.charge_type, 'form_fees')
        self.assertEqual(si.amount, Decimal('500.00'))
        self.assertEqual(si.loan, self.loan)

    def test_standing_instruction_charge_types(self):
        for ct, _ in StandingInstruction.CHARGE_TYPE_CHOICES:
            si = StandingInstruction.objects.create(
                loan=self.loan,
                branch=self.head_office,
                charge_type=ct,
                amount=Decimal('100.00'),
                charge_date=date(2024, 3, 1),
                narration=f'Test {ct}',
                created_by=self.cashier_user,
            )
            self.assertEqual(si.charge_type, ct)

    def test_add_standing_instruction_service(self):
        original_principal = self.loan.outstanding_principal
        si = add_standing_instruction(
            loan=self.loan,
            charge_type='legal_fees',
            amount=Decimal('2000.00'),
            branch=self.head_office,
            narration='Legal fees for notice',
            created_by=self.cashier_user,
        )
        self.loan.refresh_from_db()
        self.assertEqual(si.amount, Decimal('2000.00'))
        self.assertEqual(
            self.loan.outstanding_principal,
            original_principal + Decimal('2000.00'),
        )


class GuarantorValidationTests(BaseTestCase):
    """Tests for validate_guarantor and validate_loan_application services."""

    def setUp(self):
        super().setUp()
        self.product_shareholder = LoanProduct.objects.create(
            name='Secured Loan',
            interest_rate=Decimal('12.00'),
            max_amount=Decimal('500000.00'),
            max_tenure_months=60,
            interest_type='reducing_monthly',
            requires_guarantor=True,
            guarantor_must_be_shareholder=True,
            allow_multiple=False,
            is_active=True,
        )
        self.product_no_shareholder = LoanProduct.objects.create(
            name='Unsecured Loan',
            interest_rate=Decimal('14.00'),
            max_amount=Decimal('100000.00'),
            max_tenure_months=24,
            interest_type='flat',
            requires_guarantor=True,
            guarantor_must_be_shareholder=False,
            allow_multiple=False,
            is_active=True,
        )

    def test_validate_loan_application_no_shares(self):
        errors = validate_loan_application(
            self.member1,
            self.product_shareholder,
            Decimal('100000.00'),
        )
        self.assertTrue(len(errors) > 0)
        self.assertIn('shares', errors[0].lower())

    def test_validate_loan_application_no_existing_loan(self):
        ShareHolding.objects.create(
            member=self.member1, branch=self.head_office,
            share_count=10, face_value_per_share=100,
            total_amount=1000, purchase_date=date(2024, 1, 1),
            status='active', created_by=self.admin_user,
        )
        errors = validate_loan_application(
            self.member1,
            self.product_shareholder,
            Decimal('100000.00'),
        )
        self.assertEqual(len(errors), 0)

    def test_validate_loan_application_duplicate_regular(self):
        ShareHolding.objects.create(
            member=self.member1, branch=self.head_office,
            share_count=10, face_value_per_share=100,
            total_amount=1000, purchase_date=date(2024, 1, 1),
            status='active', created_by=self.admin_user,
        )
        LoanAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            loan_product=self.product_shareholder,
            loan_no='LN-VAL-001',
            applied_date=date(2024, 1, 1),
            applied_amount=Decimal('100000.00'),
            interest_rate=Decimal('12.00'),
            tenure_months=12,
            status='disbursed',
            outstanding_principal=Decimal('80000.00'),
        )
        errors = validate_loan_application(
            self.member1,
            self.product_shareholder,
            Decimal('50000.00'),
        )
        self.assertTrue(len(errors) > 0)
        self.assertIn('active', errors[0].lower())

    def test_get_active_guarantee_count(self):
        product = LoanProduct.objects.create(
            name='Test',
            interest_rate=Decimal('12.00'),
            max_amount=Decimal('500000.00'),
            max_tenure_months=60,
            is_active=True,
        )
        loan = LoanAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            loan_product=product,
            loan_no='LN-GC-010',
            applied_date=date(2024, 1, 1),
            applied_amount=Decimal('100000.00'),
            interest_rate=Decimal('12.00'),
            tenure_months=12,
            status='disbursed',
            outstanding_principal=Decimal('100000.00'),
        )
        LoanGuarantor.objects.create(
            loan=loan,
            guarantor_member=self.member2,
            guarantee_amount=Decimal('100000.00'),
        )
        count = get_active_guarantee_count(self.member2)
        self.assertEqual(count, 1)
