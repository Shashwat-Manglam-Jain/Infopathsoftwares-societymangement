from datetime import date, timedelta
from decimal import Decimal

from apps.accounting.models import ChartOfAccounts
from apps.dayend.models import DayEndLog, FinancialYear, MonthEndLog, WorkingDay, YearEndLog
from apps.dayend.services import (
    begin_working_day,
    rollback_day_end,
    run_day_end,
    run_month_end,
    run_year_end,
)
from apps.loans.models import EMISchedule, LoanAccount, LoanProduct
from apps.loans.services import approve_loan, disburse_loan
from apps.savings.models import SavingsAccount

from .base import BaseTestCase


class DayEndProcessingTests(BaseTestCase):
    """Tests for day-end batch processing."""

    def setUp(self):
        super().setUp()
        self._setup_coa()
        self._setup_financial_year()

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
            code='2001',
            name='Savings Deposits',
            account_group='liability',
            account_type='deposits_taken',
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
            code='3003',
            name='Penal Interest',
            account_group='income',
            account_type='other',
            is_system=True,
        )
        ChartOfAccounts.objects.create(
            code='4001',
            name='Interest on Savings',
            account_group='expense',
            account_type='interest_expense',
            is_system=True,
        )

    def _setup_financial_year(self):
        self.fy = FinancialYear.objects.create(
            fy_code='2024-25',
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31),
            is_current=True,
        )

    def test_day_end_creates_log(self):
        """Running day-end creates a DayEndLog entry."""
        begin_working_day(self.head_office, date(2024, 6, 15), self.admin_user)
        run_day_end(self.head_office, self.admin_user)
        log = DayEndLog.objects.filter(
            branch=self.head_office,
            processing_date=date(2024, 6, 15),
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.status, 'completed')
        self.assertIsNotNone(log.completed_at)

    def test_day_end_accrues_savings_interest(self):
        """Day-end accrues interest on all active savings accounts in the branch."""
        account = SavingsAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            account_type='savings',
            opening_date=date(2024, 1, 1),
            status='active',
            current_balance=Decimal('100000.00'),
            interest_rate=Decimal('6.00'),
            created_by=self.cashier_user,
        )

        begin_working_day(self.head_office, date(2024, 6, 15), self.admin_user)
        run_day_end(self.head_office, self.admin_user)
        log = DayEndLog.objects.filter(
            branch=self.head_office,
            processing_date=date(2024, 6, 15),
        ).first()
        self.assertGreaterEqual(log.savings_interest_accrued_count, 1)

    def test_day_end_accrues_loan_interest(self):
        """Day-end accrues interest on all disbursed loans in the branch."""
        product = LoanProduct.objects.create(
            name='Personal Loan',
            interest_rate=Decimal('12.00'),
            max_amount=Decimal('500000.00'),
            max_tenure_months=60,
            interest_type='reducing_monthly',
            npa_days_threshold=90,
            is_active=True,
        )
        loan = LoanAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            loan_product=product,
            loan_no='LN-DE-001',
            applied_date=date(2024, 1, 1),
            applied_amount=Decimal('100000.00'),
            interest_rate=Decimal('12.00'),
            tenure_months=12,
            status='applied',
            created_by=self.cashier_user,
        )
        approve_loan(loan, Decimal('100000.00'), self.manager_user)
        disburse_loan(loan, self.head_office, self.cashier_user)

        begin_working_day(self.head_office, date(2024, 6, 15), self.admin_user)
        run_day_end(self.head_office, self.admin_user)
        log = DayEndLog.objects.filter(
            branch=self.head_office,
            processing_date=date(2024, 6, 15),
        ).first()
        self.assertGreaterEqual(log.loan_interest_accrued_count, 1)

    def test_day_end_marks_overdue(self):
        """Day-end marks EMIs with due_date in the past as overdue."""
        product = LoanProduct.objects.create(
            name='Test Loan',
            interest_rate=Decimal('12.00'),
            max_amount=Decimal('500000.00'),
            max_tenure_months=60,
            interest_type='reducing_monthly',
            npa_days_threshold=90,
            is_active=True,
        )
        loan = LoanAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            loan_product=product,
            loan_no='LN-DE-002',
            applied_date=date(2024, 1, 1),
            applied_amount=Decimal('50000.00'),
            interest_rate=Decimal('12.00'),
            tenure_months=12,
            status='applied',
            created_by=self.cashier_user,
        )
        approve_loan(loan, Decimal('50000.00'), self.manager_user)
        disburse_loan(loan, self.head_office, self.cashier_user)

        # Set first EMI due date to the past
        first_emi = EMISchedule.objects.filter(loan=loan, installment_no=1).first()
        first_emi.due_date = date.today() - timedelta(days=10)
        first_emi.save()

        begin_working_day(self.head_office, date.today(), self.admin_user)
        run_day_end(self.head_office, self.admin_user)

        first_emi.refresh_from_db()
        self.assertEqual(first_emi.status, 'overdue')

        log = DayEndLog.objects.filter(
            branch=self.head_office,
            processing_date=date.today(),
        ).first()
        self.assertGreaterEqual(log.loans_marked_overdue_count, 1)

    def test_day_end_marks_npa(self):
        """Day-end classifies loans with overdue EMIs > 90 days as NPA."""
        product = LoanProduct.objects.create(
            name='Test Loan',
            interest_rate=Decimal('12.00'),
            max_amount=Decimal('500000.00'),
            max_tenure_months=60,
            interest_type='reducing_monthly',
            npa_days_threshold=90,
            is_active=True,
        )
        loan = LoanAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            loan_product=product,
            loan_no='LN-DE-003',
            applied_date=date(2024, 1, 1),
            applied_amount=Decimal('50000.00'),
            interest_rate=Decimal('12.00'),
            tenure_months=12,
            status='disbursed',
            outstanding_principal=Decimal('50000.00'),
            overdue_days=95,
            overdue_amount=Decimal('5000.00'),
            created_by=self.cashier_user,
        )
        EMISchedule.objects.create(
            loan=loan,
            installment_no=1,
            due_date=date.today() - timedelta(days=100),
            principal_component=Decimal('4000.00'),
            interest_component=Decimal('500.00'),
            total_emi=Decimal('4500.00'),
            status='overdue',
            branch=self.head_office,
        )

        begin_working_day(self.head_office, date.today(), self.admin_user)
        run_day_end(self.head_office, self.admin_user)

        loan.refresh_from_db()
        self.assertEqual(loan.status, 'npa')

    def test_day_end_per_branch(self):
        """Day-end only processes accounts in the specified branch."""
        SavingsAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            account_type='savings',
            opening_date=date(2024, 1, 1),
            status='active',
            current_balance=Decimal('50000.00'),
            interest_rate=Decimal('6.00'),
            created_by=self.cashier_user,
        )
        SavingsAccount.objects.create(
            member=self.member2,
            branch=self.branch_a,
            account_type='savings',
            opening_date=date(2024, 1, 1),
            status='active',
            current_balance=Decimal('50000.00'),
            interest_rate=Decimal('6.00'),
            created_by=self.branch_cashier,
        )

        begin_working_day(self.head_office, date(2024, 6, 15), self.admin_user)
        run_day_end(self.head_office, self.admin_user)

        # Only HO log should exist
        ho_log = DayEndLog.objects.filter(
            branch=self.head_office,
            processing_date=date(2024, 6, 15),
        ).first()
        br_log = DayEndLog.objects.filter(
            branch=self.branch_a,
            processing_date=date(2024, 6, 15),
        ).first()
        self.assertIsNotNone(ho_log)
        self.assertIsNone(br_log)

    def test_day_end_idempotent(self):
        """Running day-end twice for the same date raises ValueError."""
        SavingsAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            account_type='savings',
            opening_date=date(2024, 1, 1),
            status='active',
            current_balance=Decimal('50000.00'),
            interest_rate=Decimal('6.00'),
            created_by=self.cashier_user,
        )

        begin_working_day(self.head_office, date(2024, 6, 15), self.admin_user)
        run_day_end(self.head_office, self.admin_user)

        # Re-open day then try run_day_end again — should raise because DayEndLog already completed
        begin_working_day(self.head_office, date(2024, 6, 15), self.admin_user)
        with self.assertRaises(ValueError):
            run_day_end(self.head_office, self.admin_user)

        logs = DayEndLog.objects.filter(
            branch=self.head_office,
            processing_date=date(2024, 6, 15),
            status='completed',
        )
        self.assertEqual(logs.count(), 1)


class FinancialYearTests(BaseTestCase):
    """Tests for financial year management."""

    def test_create_financial_year(self):
        """Financial year stores code, dates, and current status."""
        fy = FinancialYear.objects.create(
            fy_code='2025-26',
            start_date=date(2025, 4, 1),
            end_date=date(2026, 3, 31),
            is_current=True,
        )
        self.assertEqual(fy.fy_code, '2025-26')
        self.assertFalse(fy.is_closed)

    def test_financial_year_close(self):
        """Closing a financial year sets is_closed and records who closed it."""
        fy = FinancialYear.objects.create(
            fy_code='2024-25',
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31),
            is_current=True,
        )
        fy.is_closed = True
        fy.is_current = False
        fy.closed_by = self.admin_user
        fy.closed_at = date(2025, 4, 5)
        fy.save()
        fy.refresh_from_db()
        self.assertTrue(fy.is_closed)
        self.assertFalse(fy.is_current)
        self.assertEqual(fy.closed_by, self.admin_user)


class WorkingDayTests(BaseTestCase):
    """Tests for WorkingDay model and begin_working_day service."""

    def setUp(self):
        super().setUp()
        self._setup_coa()
        self._setup_financial_year()

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
            code='2001',
            name='Savings',
            account_group='liability',
            account_type='deposits_taken',
            is_system=True,
        )

    def _setup_financial_year(self):
        self.fy = FinancialYear.objects.create(
            fy_code='2024-25',
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31),
            is_current=True,
        )

    def test_begin_working_day_creates_record(self):
        wd = begin_working_day(self.head_office, date(2024, 6, 15), self.admin_user)
        self.assertEqual(wd.current_date, date(2024, 6, 15))
        self.assertTrue(wd.is_day_open)
        self.assertEqual(wd.opened_by, self.admin_user)

    def test_begin_day_already_open_raises(self):
        begin_working_day(self.head_office, date(2024, 6, 15), self.admin_user)
        with self.assertRaises(ValueError) as ctx:
            begin_working_day(self.head_office, date(2024, 6, 16), self.admin_user)
        self.assertIn('already open', str(ctx.exception).lower())

    def test_begin_day_after_close(self):
        wd = begin_working_day(self.head_office, date(2024, 6, 15), self.admin_user)
        wd.is_day_open = False
        wd.day_end_completed = True
        wd.save()
        wd2 = begin_working_day(self.head_office, date(2024, 6, 16), self.admin_user)
        self.assertEqual(wd2.current_date, date(2024, 6, 16))
        self.assertEqual(wd2.last_working_date, date(2024, 6, 15))
        self.assertTrue(wd2.is_day_open)


class DayEndServicesTests(BaseTestCase):
    """Tests for run_day_end, rollback_day_end services."""

    def setUp(self):
        super().setUp()
        self._setup_coa()
        FinancialYear.objects.create(
            fy_code='2024-25',
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31),
            is_current=True,
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
            code='2001',
            name='Savings',
            account_group='liability',
            account_type='deposits_taken',
            is_system=True,
            related_table_name='saving',
        )
        ChartOfAccounts.objects.create(
            code='1003',
            name='Loans',
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
            code='3003',
            name='Penal Interest',
            account_group='income',
            account_type='other',
            is_system=True,
        )

    def test_run_day_end_requires_open_day(self):
        with self.assertRaises(WorkingDay.DoesNotExist):
            run_day_end(self.head_office, self.admin_user)

    def test_run_day_end_closes_day(self):
        begin_working_day(self.head_office, date(2024, 6, 15), self.admin_user)
        log = run_day_end(self.head_office, self.admin_user)
        self.assertEqual(log.status, 'completed')
        self.assertEqual(log.processing_date, date(2024, 6, 15))
        wd = WorkingDay.objects.get(branch=self.head_office)
        self.assertFalse(wd.is_day_open)
        self.assertTrue(wd.day_end_completed)

    def test_run_day_end_not_open_raises(self):
        wd = begin_working_day(self.head_office, date(2024, 6, 15), self.admin_user)
        wd.is_day_open = False
        wd.save()
        with self.assertRaises(ValueError) as ctx:
            run_day_end(self.head_office, self.admin_user)
        self.assertIn('no working day', str(ctx.exception).lower())

    def test_run_day_end_already_completed_raises(self):
        begin_working_day(self.head_office, date(2024, 6, 15), self.admin_user)
        run_day_end(self.head_office, self.admin_user)
        begin_working_day(self.head_office, date(2024, 6, 15), self.admin_user)
        with self.assertRaises(ValueError) as ctx:
            run_day_end(self.head_office, self.admin_user)
        self.assertIn('already completed', str(ctx.exception).lower())

    def test_rollback_day_end(self):
        begin_working_day(self.head_office, date(2024, 6, 15), self.admin_user)
        run_day_end(self.head_office, self.admin_user)
        log = rollback_day_end(self.head_office, date(2024, 6, 15), self.admin_user)
        self.assertEqual(log.status, 'rolled_back')
        wd = WorkingDay.objects.get(branch=self.head_office)
        self.assertTrue(wd.is_day_open)
        self.assertFalse(wd.day_end_completed)

    def test_rollback_no_completed_day_raises(self):
        with self.assertRaises(ValueError) as ctx:
            rollback_day_end(self.head_office, date(2024, 6, 15), self.admin_user)
        self.assertIn('no completed', str(ctx.exception).lower())

    def test_run_day_end_with_savings(self):
        SavingsAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            account_no='SA0001',
            account_type='savings',
            opening_date=date(2024, 1, 1),
            status='active',
            current_balance=Decimal('100000.00'),
            interest_rate=Decimal('6.00'),
        )
        begin_working_day(self.head_office, date(2024, 6, 15), self.admin_user)
        log = run_day_end(self.head_office, self.admin_user)
        self.assertGreaterEqual(log.savings_interest_accrued_count, 1)

    def test_run_day_end_with_loans(self):
        product = LoanProduct.objects.create(
            name='Test Loan',
            interest_rate=Decimal('12.00'),
            max_amount=Decimal('500000.00'),
            max_tenure_months=60,
            interest_type='reducing_monthly',
            npa_days_threshold=90,
            is_active=True,
        )
        loan = LoanAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            loan_product=product,
            loan_no='LN-SVC-001',
            applied_date=date(2024, 1, 1),
            applied_amount=Decimal('100000.00'),
            interest_rate=Decimal('12.00'),
            tenure_months=12,
            status='disbursed',
            outstanding_principal=Decimal('100000.00'),
        )
        begin_working_day(self.head_office, date(2024, 6, 15), self.admin_user)
        log = run_day_end(self.head_office, self.admin_user)
        self.assertGreaterEqual(log.loan_interest_accrued_count, 1)


class MonthEndServicesTests(BaseTestCase):
    """Tests for run_month_end service."""

    def setUp(self):
        super().setUp()
        ChartOfAccounts.objects.create(
            code='1001',
            name='Cash',
            account_group='asset',
            account_type='cash',
            is_system=True,
            branch=self.head_office,
        )
        ChartOfAccounts.objects.create(
            code='1003',
            name='Loans',
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
            code='3003',
            name='Penal Interest',
            account_group='income',
            account_type='other',
            is_system=True,
        )

    def test_run_month_end(self):
        log = run_month_end(self.head_office, date(2024, 6, 1), self.admin_user)
        self.assertEqual(log.status, 'completed')
        self.assertEqual(log.month, date(2024, 6, 1))

    def test_run_month_end_duplicate_raises(self):
        run_month_end(self.head_office, date(2024, 6, 1), self.admin_user)
        with self.assertRaises(ValueError) as ctx:
            run_month_end(self.head_office, date(2024, 6, 1), self.admin_user)
        self.assertIn('already completed', str(ctx.exception).lower())

    def test_run_month_end_with_loan_interest(self):
        product = LoanProduct.objects.create(
            name='Test',
            interest_rate=Decimal('12.00'),
            max_amount=Decimal('500000.00'),
            max_tenure_months=60,
            interest_type='reducing_monthly',
            npa_days_threshold=90,
            is_active=True,
        )
        loan = LoanAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            loan_product=product,
            loan_no='LN-ME-001',
            applied_date=date(2024, 1, 1),
            applied_amount=Decimal('100000.00'),
            interest_rate=Decimal('12.00'),
            tenure_months=12,
            status='disbursed',
            outstanding_principal=Decimal('100000.00'),
        )
        log = run_month_end(self.head_office, date(2024, 6, 1), self.admin_user)
        self.assertGreaterEqual(log.loan_interest_calculated_count, 1)


class YearEndServicesTests(BaseTestCase):
    """Tests for run_year_end service."""

    def setUp(self):
        super().setUp()
        self.income_account = ChartOfAccounts.objects.create(
            code='3101',
            name='Interest Income',
            account_group='income',
            account_type='interest_income',
            is_system=True,
            current_balance=Decimal('50000.00'),
        )
        self.expense_account = ChartOfAccounts.objects.create(
            code='4001',
            name='Interest Expense',
            account_group='expense',
            account_type='interest_expense',
            is_system=True,
            current_balance=Decimal('20000.00'),
        )
        ChartOfAccounts.objects.create(
            code='1001',
            name='Cash',
            account_group='asset',
            account_type='cash',
            is_system=True,
            current_balance=Decimal('100000.00'),
        )
        self.fy = FinancialYear.objects.create(
            fy_code='2024-25',
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31),
            is_current=True,
        )

    def test_run_year_end(self):
        log = run_year_end(self.head_office, self.fy, self.admin_user)
        self.assertEqual(log.status, 'completed')
        self.fy.refresh_from_db()
        self.assertTrue(self.fy.is_closed)
        self.assertEqual(self.fy.closed_by, self.admin_user)

    def test_run_year_end_zeroes_pl_accounts(self):
        run_year_end(self.head_office, self.fy, self.admin_user)
        self.income_account.refresh_from_db()
        self.expense_account.refresh_from_db()
        self.assertEqual(self.income_account.current_balance, Decimal('0.00'))
        self.assertEqual(self.expense_account.current_balance, Decimal('0.00'))

    def test_run_year_end_duplicate_raises(self):
        run_year_end(self.head_office, self.fy, self.admin_user)
        with self.assertRaises(ValueError) as ctx:
            run_year_end(self.head_office, self.fy, self.admin_user)
        self.assertIn('already completed', str(ctx.exception).lower())


class MonthEndLogModelTests(BaseTestCase):
    """Tests for MonthEndLog model."""

    def test_create_month_end_log(self):
        log = MonthEndLog.objects.create(
            branch=self.head_office,
            month=date(2024, 6, 1),
            status='completed',
            loan_interest_calculated_count=5,
            demand_generated_count=3,
            rd_installments_due_count=2,
            run_by=self.admin_user,
        )
        self.assertEqual(str(log), f'{self.head_office.branch_name} - Jun 2024 - completed')

    def test_month_end_log_unique_per_branch_month(self):
        from django.db import IntegrityError

        MonthEndLog.objects.create(
            branch=self.head_office,
            month=date(2024, 6, 1),
            status='completed',
        )
        with self.assertRaises(IntegrityError):
            MonthEndLog.objects.create(
                branch=self.head_office,
                month=date(2024, 6, 1),
                status='running',
            )


class YearEndLogModelTests(BaseTestCase):
    """Tests for YearEndLog model."""

    def test_create_year_end_log(self):
        fy = FinancialYear.objects.create(
            fy_code='2024-25',
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31),
            is_current=True,
        )
        log = YearEndLog.objects.create(
            financial_year=fy,
            branch=self.head_office,
            status='completed',
            pl_accounts_zeroed=10,
            opening_balances_updated=20,
            profit_or_loss=Decimal('30000.00'),
            run_by=self.admin_user,
        )
        self.assertEqual(log.profit_or_loss, Decimal('30000.00'))
        self.assertEqual(log.status, 'completed')
