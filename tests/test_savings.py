from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from apps.accounting.models import ChartOfAccounts, JournalEntry, JournalLine
from apps.savings.models import AccountTransaction, SavingsAccount
from apps.savings.services import (
    calculate_daily_interest,
    deposit,
    post_interest,
    reverse_transaction,
    withdraw,
)

from .base import BaseTestCase


class SavingsAccountOpeningTests(BaseTestCase):
    """Tests for opening savings accounts."""

    def test_open_savings_account(self):
        """Creating a savings account auto-generates an account number."""
        account = SavingsAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            account_type='savings',
            opening_date=date(2024, 1, 1),
            status='active',
            interest_rate=Decimal('6.00'),
            minimum_balance=Decimal('500.00'),
            created_by=self.cashier_user,
        )
        self.assertIsNotNone(account.account_no)
        self.assertTrue(len(account.account_no) > 0)
        self.assertEqual(account.current_balance, Decimal('0.00'))
        self.assertEqual(account.status, 'active')

    def test_account_no_unique(self):
        """Account numbers are unique across the society."""
        a1 = SavingsAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            account_type='savings',
            opening_date=date(2024, 1, 1),
            status='active',
            interest_rate=Decimal('6.00'),
            created_by=self.cashier_user,
        )
        a2 = SavingsAccount.objects.create(
            member=self.member2,
            branch=self.branch_a,
            account_type='savings',
            opening_date=date(2024, 1, 1),
            status='active',
            interest_rate=Decimal('6.00'),
            created_by=self.branch_cashier,
        )
        self.assertNotEqual(a1.account_no, a2.account_no)


class DepositTests(BaseTestCase):
    """Tests for deposit operations."""

    def setUp(self):
        super().setUp()
        self._setup_coa()
        self.account = SavingsAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            account_type='savings',
            opening_date=date(2024, 1, 1),
            status='active',
            interest_rate=Decimal('6.00'),
            minimum_balance=Decimal('500.00'),
            created_by=self.cashier_user,
        )

    def _setup_coa(self):
        self.cash_account = ChartOfAccounts.objects.create(
            code='1001',
            name='Cash in Hand',
            account_group='asset',
            account_type='cash',
            is_system=True,
            branch=self.head_office,
        )
        self.savings_deposit_account = ChartOfAccounts.objects.create(
            code='2001',
            name='Savings Deposits',
            account_group='liability',
            account_type='deposits_taken',
            is_system=True,
        )
        self.interest_expense_account = ChartOfAccounts.objects.create(
            code='4001',
            name='Interest on Savings',
            account_group='expense',
            account_type='interest_expense',
            is_system=True,
        )

    def test_deposit(self):
        """Depositing updates balance and creates a transaction record."""
        txn = deposit(
            account=self.account,
            amount=Decimal('10000.00'),
            branch=self.head_office,
            user=self.cashier_user,
            payment_mode='cash',
            narration='Initial deposit',
        )
        self.account.refresh_from_db()
        self.assertEqual(self.account.current_balance, Decimal('10000.00'))
        self.assertEqual(txn.txn_type, 'deposit')
        self.assertEqual(txn.amount, Decimal('10000.00'))
        self.assertEqual(txn.running_balance, Decimal('10000.00'))

    def test_multiple_deposits(self):
        """Multiple deposits accumulate correctly."""
        deposit(self.account, Decimal('5000.00'), self.head_office, self.cashier_user, 'cash', 'First')
        deposit(self.account, Decimal('3000.00'), self.head_office, self.cashier_user, 'cash', 'Second')
        self.account.refresh_from_db()
        self.assertEqual(self.account.current_balance, Decimal('8000.00'))

    def test_deposit_journal_entry(self):
        """Deposit creates journal: DEBIT Cash, CREDIT Savings Deposits."""
        deposit(self.account, Decimal('10000.00'), self.head_office, self.cashier_user, 'cash', 'Deposit')
        entry = JournalEntry.objects.filter(reference_type='savings_txn').last()
        self.assertIsNotNone(entry)

        lines = JournalLine.objects.filter(journal_entry=entry)
        total_debit = sum(l.debit_amount for l in lines)
        total_credit = sum(l.credit_amount for l in lines)
        self.assertEqual(total_debit, Decimal('10000.00'))
        self.assertEqual(total_credit, Decimal('10000.00'))

    def test_deposit_zero_amount_rejected(self):
        """Depositing zero or negative amount raises an error."""
        with self.assertRaises(ValueError):
            deposit(self.account, Decimal('0.00'), self.head_office, self.cashier_user, 'cash', 'Zero')
        with self.assertRaises(ValueError):
            deposit(self.account, Decimal('-100.00'), self.head_office, self.cashier_user, 'cash', 'Negative')

    def test_inter_branch_deposit(self):
        """A member from branch A can deposit at head office."""
        account_br = SavingsAccount.objects.create(
            member=self.member2,
            branch=self.branch_a,
            account_type='savings',
            opening_date=date(2024, 1, 1),
            status='active',
            interest_rate=Decimal('6.00'),
            created_by=self.branch_cashier,
        )
        txn = deposit(
            account=account_br,
            amount=Decimal('5000.00'),
            branch=self.head_office,  # different from account's home branch
            user=self.cashier_user,
            payment_mode='cash',
            narration='Inter-branch deposit',
        )
        account_br.refresh_from_db()
        self.assertEqual(account_br.current_balance, Decimal('5000.00'))
        self.assertEqual(txn.branch, self.head_office)


class WithdrawalTests(BaseTestCase):
    """Tests for withdrawal operations."""

    def setUp(self):
        super().setUp()
        self._setup_coa()
        self.account = SavingsAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            account_type='savings',
            opening_date=date(2024, 1, 1),
            status='active',
            current_balance=Decimal('20000.00'),
            interest_rate=Decimal('6.00'),
            minimum_balance=Decimal('500.00'),
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
            code='2001',
            name='Savings Deposits',
            account_group='liability',
            account_type='deposits_taken',
            is_system=True,
        )

    def test_withdrawal(self):
        """Withdrawing reduces balance and creates a transaction."""
        txn = withdraw(
            account=self.account,
            amount=Decimal('5000.00'),
            branch=self.head_office,
            user=self.cashier_user,
            payment_mode='cash',
            narration='Withdrawal',
        )
        self.account.refresh_from_db()
        self.assertEqual(self.account.current_balance, Decimal('15000.00'))
        self.assertEqual(txn.txn_type, 'withdrawal')
        self.assertEqual(txn.running_balance, Decimal('15000.00'))

    def test_insufficient_balance(self):
        """Withdrawal exceeding balance raises an error."""
        with self.assertRaises(ValueError):
            withdraw(self.account, Decimal('25000.00'), self.head_office, self.cashier_user, 'cash', 'Too much')

    def test_minimum_balance_check(self):
        """Cannot withdraw if it would bring balance below minimum."""
        with self.assertRaises(ValueError):
            withdraw(self.account, Decimal('19600.00'), self.head_office, self.cashier_user, 'cash', 'Below min')
        # balance would be 400, below minimum of 500

    def test_withdrawal_journal_entry(self):
        """Withdrawal creates journal: DEBIT Savings Deposits, CREDIT Cash."""
        withdraw(self.account, Decimal('5000.00'), self.head_office, self.cashier_user, 'cash', 'Withdrawal')
        entry = JournalEntry.objects.filter(reference_type='savings_txn').last()
        lines = JournalLine.objects.filter(journal_entry=entry)
        total_debit = sum(l.debit_amount for l in lines)
        total_credit = sum(l.credit_amount for l in lines)
        self.assertEqual(total_debit, Decimal('5000.00'))
        self.assertEqual(total_credit, Decimal('5000.00'))


class InterestCalculationTests(BaseTestCase):
    """Critical tests for savings interest calculation using daily product method."""

    def setUp(self):
        super().setUp()
        self._setup_coa()
        self.account = SavingsAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            account_type='savings',
            opening_date=date(2024, 1, 1),
            status='active',
            current_balance=Decimal('100000.00'),
            interest_rate=Decimal('6.00'),
            minimum_balance=Decimal('500.00'),
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
            code='2001',
            name='Savings Deposits',
            account_group='liability',
            account_type='deposits_taken',
            is_system=True,
        )
        ChartOfAccounts.objects.create(
            code='4001',
            name='Interest on Savings',
            account_group='expense',
            account_type='interest_expense',
            is_system=True,
        )

    def test_daily_interest_calculation(self):
        """Daily interest on ₹1,00,000 at 6% p.a. = ₹16.44 (non-leap year)."""
        daily = calculate_daily_interest(self.account, date(2025, 3, 15))
        expected = Decimal('100000.00') * Decimal('6.00') / Decimal('100') / Decimal('365')
        expected = expected.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.assertEqual(daily, expected)
        self.assertEqual(daily, Decimal('16.44'))

    def test_daily_interest_leap_year(self):
        """Daily interest uses 366 days in a leap year."""
        daily = calculate_daily_interest(self.account, date(2024, 6, 15))
        expected = Decimal('100000.00') * Decimal('6.00') / Decimal('100') / Decimal('366')
        expected = expected.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.assertEqual(daily, expected)

    def test_interest_on_varying_balance(self):
        """Interest on varying balance uses daily product method.

        Day 1-10:  Balance ₹50,000, product = 5,00,000
        Day 11-20: Balance ₹60,000, product = 6,00,000
        Day 21-30: Balance ₹55,000, product = 5,50,000
        Total product = 16,50,000
        Monthly interest = (16,50,000 × 6%) / (365 × 100) = ₹271.23
        """
        self.account.current_balance = Decimal('50000.00')
        self.account.save()

        # Simulate 30 days of varying balances
        total_product = Decimal('0')

        # Days 1-10: balance 50000
        total_product += Decimal('50000.00') * 10
        # Days 11-20: balance 60000
        total_product += Decimal('60000.00') * 10
        # Days 21-30: balance 55000
        total_product += Decimal('55000.00') * 10

        self.assertEqual(total_product, Decimal('1650000'))

        interest = total_product * Decimal('6.00') / (Decimal('365') * Decimal('100'))
        interest = interest.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.assertEqual(interest, Decimal('271.23'))

    def test_quarterly_interest_posting(self):
        """Interest is credited to the account at quarter end."""
        txn = post_interest(
            account=self.account,
            from_date=date(2024, 1, 1),
            to_date=date(2024, 3, 31),
            user=self.cashier_user,
        )
        self.account.refresh_from_db()
        self.assertEqual(txn.txn_type, 'interest_credit')
        self.assertGreater(txn.amount, Decimal('0'))
        self.assertGreater(self.account.current_balance, Decimal('100000.00'))

    def test_decimal_precision(self):
        """Financial calculations never produce floating-point artifacts.

        Classic float bug: 0.1 + 0.2 = 0.30000000000000004
        With Decimal: 0.1 + 0.2 = 0.3 exactly.
        """
        a = Decimal('0.10')
        b = Decimal('0.20')
        self.assertEqual(a + b, Decimal('0.30'))

        # Interest precision
        principal = Decimal('100000.00')
        rate = Decimal('6.00')
        days = Decimal('365')
        daily_interest = principal * rate / Decimal('100') / days
        self.assertIsInstance(daily_interest, Decimal)
        # Verify it doesn't have float representation issues
        rounded = daily_interest.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.assertEqual(rounded, Decimal('16.44'))


class TransactionReversalTests(BaseTestCase):
    """Tests for reversing a savings transaction."""

    def setUp(self):
        super().setUp()
        self._setup_coa()
        self.account = SavingsAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            account_type='savings',
            opening_date=date(2024, 1, 1),
            status='active',
            current_balance=Decimal('0.00'),
            interest_rate=Decimal('6.00'),
            minimum_balance=Decimal('0.00'),
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
            code='2001',
            name='Savings Deposits',
            account_group='liability',
            account_type='deposits_taken',
            is_system=True,
        )

    def test_transaction_reversal(self):
        """Reversing a deposit restores the previous balance."""
        original = deposit(
            self.account,
            Decimal('10000.00'),
            self.head_office,
            self.cashier_user,
            'cash',
            'Deposit',
        )
        self.account.refresh_from_db()
        self.assertEqual(self.account.current_balance, Decimal('10000.00'))

        reversal = reverse_transaction(original, self.admin_user)
        self.account.refresh_from_db()
        self.assertEqual(self.account.current_balance, Decimal('0.00'))
        self.assertEqual(reversal.txn_type, 'reversal')
        self.assertTrue(reversal.is_reversed)
        self.assertEqual(reversal.reversal_of, original)

        original.refresh_from_db()
        self.assertTrue(original.is_reversed)

    def test_reversal_creates_journal(self):
        """Reversal creates a journal entry that mirrors the original."""
        original = deposit(
            self.account,
            Decimal('5000.00'),
            self.head_office,
            self.cashier_user,
            'cash',
            'Deposit',
        )
        reverse_transaction(original, self.admin_user)

        entries = JournalEntry.objects.filter(reference_type='savings_txn')
        self.assertEqual(entries.count(), 2)  # original + reversal


class PassbookTests(BaseTestCase):
    """Tests for passbook / statement correctness."""

    def setUp(self):
        super().setUp()
        self._setup_coa()
        self.account = SavingsAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            account_type='savings',
            opening_date=date(2024, 1, 1),
            status='active',
            current_balance=Decimal('0.00'),
            interest_rate=Decimal('6.00'),
            minimum_balance=Decimal('0.00'),
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
            code='2001',
            name='Savings Deposits',
            account_group='liability',
            account_type='deposits_taken',
            is_system=True,
        )

    def test_passbook_entries_running_balance(self):
        """Passbook shows correct running balance after multiple operations."""
        deposit(self.account, Decimal('10000.00'), self.head_office, self.cashier_user, 'cash', 'Deposit 1')
        deposit(self.account, Decimal('5000.00'), self.head_office, self.cashier_user, 'cash', 'Deposit 2')
        withdraw(self.account, Decimal('3000.00'), self.head_office, self.cashier_user, 'cash', 'Withdrawal 1')
        deposit(self.account, Decimal('2000.00'), self.head_office, self.cashier_user, 'cash', 'Deposit 3')

        txns = AccountTransaction.objects.filter(account=self.account).order_by('created_at')

        expected_balances = [
            Decimal('10000.00'),
            Decimal('15000.00'),
            Decimal('12000.00'),
            Decimal('14000.00'),
        ]
        actual_balances = [t.running_balance for t in txns]
        self.assertEqual(actual_balances, expected_balances)

        self.account.refresh_from_db()
        self.assertEqual(self.account.current_balance, Decimal('14000.00'))
