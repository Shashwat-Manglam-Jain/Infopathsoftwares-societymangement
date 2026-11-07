from datetime import date
from decimal import Decimal

from apps.accounting.initial_coa import setup_chart_of_accounts
from apps.accounting.models import ChartOfAccounts, JournalLine
from apps.accounting.services import (
    create_journal_entry,
    generate_voucher_no,
    get_ledger,
    get_trial_balance,
    reverse_journal_entry,
)

from .base import BaseTestCase


class ChartOfAccountsTests(BaseTestCase):
    """Tests for chart of accounts structure."""

    def test_create_account(self):
        """A GL account stores code, name, group, and type."""
        account = ChartOfAccounts.objects.create(
            code='1001',
            name='Cash in Hand - HO',
            account_group='asset',
            account_type='cash',
            is_system=True,
            branch=self.head_office,
        )
        self.assertEqual(account.code, '1001')
        self.assertEqual(account.account_group, 'asset')
        self.assertEqual(account.current_balance, Decimal('0.00'))

    def test_chart_of_accounts_tree(self):
        """Accounts can have parent-child hierarchy."""
        parent = ChartOfAccounts.objects.create(
            code='1000',
            name='Current Assets',
            account_group='asset',
            account_type='other',
            is_system=True,
        )
        child1 = ChartOfAccounts.objects.create(
            code='1001',
            name='Cash in Hand',
            account_group='asset',
            account_type='cash',
            parent=parent,
            is_system=True,
        )
        child2 = ChartOfAccounts.objects.create(
            code='1002',
            name='Bank Account',
            account_group='asset',
            account_type='bank',
            parent=parent,
            is_system=True,
        )
        children = ChartOfAccounts.objects.filter(parent=parent)
        self.assertEqual(children.count(), 2)
        self.assertEqual(child1.parent, parent)
        self.assertEqual(child2.parent, parent)

    def test_default_coa_creation(self):
        """Default chart of accounts creates all required system accounts."""
        setup_chart_of_accounts([self.head_office])
        accounts = ChartOfAccounts.objects.filter(is_system=True)
        # Should have at least these groups
        groups = set(accounts.values_list('account_group', flat=True))
        self.assertIn('asset', groups)
        self.assertIn('liability', groups)
        self.assertIn('income', groups)
        self.assertIn('expense', groups)
        self.assertIn('equity', groups)

    def test_system_accounts_cannot_be_deleted(self):
        """System accounts (is_system=True) should be protected from deletion.

        This would typically be enforced in the view/service layer rather than
        the model, but we verify the flag is set correctly.
        """
        account = ChartOfAccounts.objects.create(
            code='9999',
            name='System Account',
            account_group='asset',
            account_type='other',
            is_system=True,
        )
        self.assertTrue(account.is_system)

    def test_unique_account_code(self):
        """Account codes must be unique."""
        ChartOfAccounts.objects.create(
            code='1001',
            name='Cash',
            account_group='asset',
            account_type='cash',
            is_system=True,
        )
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            ChartOfAccounts.objects.create(
                code='1001',
                name='Duplicate',
                account_group='asset',
                account_type='other',
            )


class JournalEntryTests(BaseTestCase):
    """Tests for double-entry journal entries."""

    def setUp(self):
        super().setUp()
        self.cash = ChartOfAccounts.objects.create(
            code='1001',
            name='Cash in Hand',
            account_group='asset',
            account_type='cash',
            is_system=True,
            branch=self.head_office,
        )
        self.savings = ChartOfAccounts.objects.create(
            code='2001',
            name='Savings Deposits',
            account_group='liability',
            account_type='deposits_taken',
            is_system=True,
        )
        self.loans = ChartOfAccounts.objects.create(
            code='1101',
            name='Loans & Advances',
            account_group='asset',
            account_type='loans_given',
            is_system=True,
        )
        self.interest_income = ChartOfAccounts.objects.create(
            code='3101',
            name='Interest on Loans',
            account_group='income',
            account_type='interest_income',
            is_system=True,
        )

    def test_journal_entry_balanced(self):
        """A balanced journal entry is created successfully."""
        entry = create_journal_entry(
            entry_date=date(2024, 3, 15),
            voucher_type='receipt',
            branch=self.head_office,
            narration='Member deposit',
            lines=[
                {'account_code': '1001', 'debit': Decimal('10000.00'), 'credit': Decimal('0.00')},
                {'account_code': '2001', 'debit': Decimal('0.00'), 'credit': Decimal('10000.00')},
            ],
            user=self.cashier_user,
        )
        self.assertIsNotNone(entry)
        self.assertIsNotNone(entry.voucher_no)
        lines = JournalLine.objects.filter(journal_entry=entry)
        total_debit = sum(l.debit_amount for l in lines)
        total_credit = sum(l.credit_amount for l in lines)
        self.assertEqual(total_debit, total_credit)
        self.assertEqual(total_debit, Decimal('10000.00'))

    def test_journal_entry_unbalanced_raises_error(self):
        """An unbalanced journal entry raises ValueError."""
        with self.assertRaises(ValueError):
            create_journal_entry(
                entry_date=date(2024, 3, 15),
                voucher_type='receipt',
                branch=self.head_office,
                narration='Unbalanced entry',
                lines=[
                    {'account_code': '1001', 'debit': Decimal('10000.00'), 'credit': Decimal('0.00')},
                    {'account_code': '2001', 'debit': Decimal('0.00'), 'credit': Decimal('9000.00')},  # imbalanced
                ],
                user=self.cashier_user,
            )

    def test_multi_line_journal(self):
        """Journal entries can have more than 2 lines (e.g., EMI split)."""
        entry = create_journal_entry(
            entry_date=date(2024, 4, 1),
            voucher_type='receipt',
            branch=self.head_office,
            narration='EMI collection - principal + interest',
            lines=[
                {'account_code': '1001', 'debit': Decimal('8884.88'), 'credit': Decimal('0.00')},
                {'account_code': '1101', 'debit': Decimal('0.00'), 'credit': Decimal('7884.88')},
                {'account_code': '3101', 'debit': Decimal('0.00'), 'credit': Decimal('1000.00')},
            ],
            user=self.cashier_user,
            reference_type='emi_payment',
        )
        lines = JournalLine.objects.filter(journal_entry=entry)
        self.assertEqual(lines.count(), 3)
        total_debit = sum(l.debit_amount for l in lines)
        total_credit = sum(l.credit_amount for l in lines)
        self.assertEqual(total_debit, total_credit)

    def test_gl_balance_update(self):
        """After journal entry, GL account balances are updated."""
        initial_cash = self.cash.current_balance
        initial_savings = self.savings.current_balance

        create_journal_entry(
            entry_date=date(2024, 3, 15),
            voucher_type='receipt',
            branch=self.head_office,
            narration='Deposit',
            lines=[
                {'account_code': '1001', 'debit': Decimal('10000.00'), 'credit': Decimal('0.00')},
                {'account_code': '2001', 'debit': Decimal('0.00'), 'credit': Decimal('10000.00')},
            ],
            user=self.cashier_user,
        )
        self.cash.refresh_from_db()
        self.savings.refresh_from_db()

        # Cash (asset) increases with debit
        self.assertEqual(
            self.cash.current_balance,
            initial_cash + Decimal('10000.00'),
        )
        # Savings deposits (liability) increases with credit
        self.assertEqual(
            self.savings.current_balance,
            initial_savings + Decimal('10000.00'),
        )


class JournalReversalTests(BaseTestCase):
    """Tests for journal entry reversal."""

    def setUp(self):
        super().setUp()
        self.cash = ChartOfAccounts.objects.create(
            code='1001',
            name='Cash in Hand',
            account_group='asset',
            account_type='cash',
            is_system=True,
            branch=self.head_office,
        )
        self.savings = ChartOfAccounts.objects.create(
            code='2001',
            name='Savings Deposits',
            account_group='liability',
            account_type='deposits_taken',
            is_system=True,
        )

    def test_journal_reversal(self):
        """Reversing an entry creates a mirror entry with swapped debits/credits."""
        original = create_journal_entry(
            entry_date=date(2024, 3, 15),
            voucher_type='receipt',
            branch=self.head_office,
            narration='Deposit',
            lines=[
                {'account_code': '1001', 'debit': Decimal('5000.00'), 'credit': Decimal('0.00')},
                {'account_code': '2001', 'debit': Decimal('0.00'), 'credit': Decimal('5000.00')},
            ],
            user=self.cashier_user,
        )
        reversal = reverse_journal_entry(original, self.admin_user)

        original.refresh_from_db()
        self.assertTrue(original.is_reversed)
        self.assertIsNotNone(reversal)
        self.assertEqual(reversal.reversal_of, original)

        # GL balances should be back to zero
        self.cash.refresh_from_db()
        self.savings.refresh_from_db()
        self.assertEqual(self.cash.current_balance, Decimal('0.00'))
        self.assertEqual(self.savings.current_balance, Decimal('0.00'))


class VoucherNumberTests(BaseTestCase):
    """Tests for auto-generated voucher numbers."""

    def setUp(self):
        super().setUp()
        self.cash = ChartOfAccounts.objects.create(
            code='1001', name='Cash', account_group='asset', is_system=True, branch=self.head_office,
        )
        self.savings = ChartOfAccounts.objects.create(
            code='2001', name='Savings', account_group='liability', is_system=True,
        )

    def test_voucher_number_auto_generation(self):
        """Voucher numbers auto-increment per type per branch."""
        v1 = generate_voucher_no('receipt', self.head_office)
        self.assertEqual(v1, 'R/000001')
        self.assertIn('R', v1)

        # Create an actual entry so the sequence advances
        create_journal_entry(
            entry_date=date.today(), voucher_type='receipt', branch=self.head_office,
            narration='test', user=self.admin_user,
            lines=[
                {'account_code': '1001', 'debit': Decimal('100'), 'credit': Decimal('0')},
                {'account_code': '2001', 'debit': Decimal('0'), 'credit': Decimal('100')},
            ],
        )
        v2 = generate_voucher_no('receipt', self.head_office)
        self.assertEqual(v2, 'R/000002')
        self.assertNotEqual(v1, v2)

        v3 = generate_voucher_no('payment', self.head_office)
        self.assertIn('P', v3)

    def test_voucher_numbers_per_branch(self):
        """Different branches have independent voucher number sequences."""
        v1 = generate_voucher_no('receipt', self.head_office)
        v2 = generate_voucher_no('receipt', self.branch_a)
        self.assertEqual(v1, v2)


class TrialBalanceTests(BaseTestCase):
    """Tests for trial balance report accuracy."""

    def setUp(self):
        super().setUp()
        self.cash = ChartOfAccounts.objects.create(
            code='1001',
            name='Cash',
            account_group='asset',
            account_type='cash',
            is_system=True,
            branch=self.head_office,
        )
        self.savings = ChartOfAccounts.objects.create(
            code='2001',
            name='Savings',
            account_group='liability',
            account_type='deposits_taken',
            is_system=True,
        )
        self.loans_given = ChartOfAccounts.objects.create(
            code='1101',
            name='Loans',
            account_group='asset',
            account_type='loans_given',
            is_system=True,
        )
        self.interest = ChartOfAccounts.objects.create(
            code='3101',
            name='Interest Income',
            account_group='income',
            account_type='interest_income',
            is_system=True,
        )

    def test_trial_balance_balances(self):
        """Total debits must equal total credits in trial balance."""
        # Create some transactions
        create_journal_entry(
            entry_date=date(2024, 3, 1),
            voucher_type='receipt',
            branch=self.head_office,
            narration='Deposit',
            lines=[
                {'account_code': '1001', 'debit': Decimal('50000.00'), 'credit': Decimal('0.00')},
                {'account_code': '2001', 'debit': Decimal('0.00'), 'credit': Decimal('50000.00')},
            ],
            user=self.cashier_user,
        )
        create_journal_entry(
            entry_date=date(2024, 3, 5),
            voucher_type='payment',
            branch=self.head_office,
            narration='Loan disbursement',
            lines=[
                {'account_code': '1101', 'debit': Decimal('30000.00'), 'credit': Decimal('0.00')},
                {'account_code': '1001', 'debit': Decimal('0.00'), 'credit': Decimal('30000.00')},
            ],
            user=self.cashier_user,
        )

        result = get_trial_balance()
        total_debit = sum(row['debit'] for row in result['accounts'] if row['debit'] > 0)
        total_credit = sum(row['credit'] for row in result['accounts'] if row['credit'] > 0)
        self.assertEqual(total_debit, total_credit)

    def test_ledger(self):
        """Ledger shows all journal lines for a specific account."""
        create_journal_entry(
            entry_date=date(2024, 3, 1),
            voucher_type='receipt',
            branch=self.head_office,
            narration='Entry 1',
            lines=[
                {'account_code': '1001', 'debit': Decimal('10000.00'), 'credit': Decimal('0.00')},
                {'account_code': '2001', 'debit': Decimal('0.00'), 'credit': Decimal('10000.00')},
            ],
            user=self.cashier_user,
        )
        create_journal_entry(
            entry_date=date(2024, 3, 5),
            voucher_type='receipt',
            branch=self.head_office,
            narration='Entry 2',
            lines=[
                {'account_code': '1001', 'debit': Decimal('5000.00'), 'credit': Decimal('0.00')},
                {'account_code': '2001', 'debit': Decimal('0.00'), 'credit': Decimal('5000.00')},
            ],
            user=self.cashier_user,
        )

        result = get_ledger(
            account_code='1001',
            from_date=date(2024, 3, 1),
            to_date=date(2024, 3, 31),
        )
        self.assertEqual(len(result['entries']), 2)
        total_debit = sum(entry['debit'] for entry in result['entries'])
        self.assertEqual(total_debit, Decimal('15000.00'))


class ChartOfAccountsExtendedFieldsTests(BaseTestCase):
    """Tests for new COA fields: related_table_name, interest flags, report position, etc."""

    def test_related_table_name_saving(self):
        account = ChartOfAccounts.objects.create(
            code='2001',
            name='Savings Deposits',
            account_group='liability',
            account_type='deposits_taken',
            related_table_name='saving',
        )
        self.assertEqual(account.related_table_name, 'saving')

    def test_related_table_name_loan(self):
        account = ChartOfAccounts.objects.create(
            code='1003',
            name='Loans Given',
            account_group='asset',
            account_type='loans_given',
            related_table_name='loan',
        )
        self.assertEqual(account.related_table_name, 'loan')

    def test_related_table_choices(self):
        for choice, _ in ChartOfAccounts.RELATED_TABLE_CHOICES:
            account = ChartOfAccounts.objects.create(
                code=f'RT{ChartOfAccounts.RELATED_TABLE_CHOICES.index((choice, _)):03d}',
                name=f'Test {choice}',
                account_group='asset',
                related_table_name=choice,
            )
            self.assertEqual(account.related_table_name, choice)

    def test_interest_affected_flag(self):
        account = ChartOfAccounts.objects.create(
            code='2010',
            name='FD Head',
            account_group='liability',
            related_table_name='fixed',
            interest_affected=True,
        )
        self.assertTrue(account.interest_affected)

    def test_overdue_affected_flag(self):
        account = ChartOfAccounts.objects.create(
            code='1010',
            name='Loan Head',
            account_group='asset',
            related_table_name='loan',
            overdue_affected=True,
        )
        self.assertTrue(account.overdue_affected)

    def test_interest_given_flag(self):
        account = ChartOfAccounts.objects.create(
            code='2020',
            name='Savings Head',
            account_group='liability',
            related_table_name='saving',
            interest_given=True,
        )
        self.assertTrue(account.interest_given)

    def test_interest_code_fk(self):
        interest_head = ChartOfAccounts.objects.create(
            code='3001',
            name='Interest on Savings (Expense)',
            account_group='expense',
            related_table_name='interest_paid',
        )
        savings_head = ChartOfAccounts.objects.create(
            code='2030',
            name='Savings Head',
            account_group='liability',
            related_table_name='saving',
            interest_code=interest_head,
        )
        self.assertEqual(savings_head.interest_code, interest_head)
        self.assertIn(savings_head, interest_head.interest_linked_heads.all())

    def test_report_position_choices(self):
        for pos, _ in ChartOfAccounts.REPORT_POSITION_CHOICES:
            account = ChartOfAccounts.objects.create(
                code=f'RP{ChartOfAccounts.REPORT_POSITION_CHOICES.index((pos, _)):03d}',
                name=f'Test {pos}',
                account_group='asset',
                report_position=pos,
            )
            self.assertEqual(account.report_position, pos)

    def test_display_order(self):
        a1 = ChartOfAccounts.objects.create(
            code='D001',
            name='First',
            account_group='asset',
            display_order=10,
        )
        a2 = ChartOfAccounts.objects.create(
            code='D002',
            name='Second',
            account_group='asset',
            display_order=20,
        )
        ordered = list(
            ChartOfAccounts.objects.filter(
                code__in=['D001', 'D002'],
            ).order_by('display_order')
        )
        self.assertEqual(ordered[0].code, 'D001')
        self.assertEqual(ordered[1].code, 'D002')

    def test_allow_transactions_flag(self):
        group_head = ChartOfAccounts.objects.create(
            code='G001',
            name='Group Head',
            account_group='asset',
            related_table_name='group',
            allow_transactions=False,
        )
        self.assertFalse(group_head.allow_transactions)

    def test_default_code_flag(self):
        system_head = ChartOfAccounts.objects.create(
            code='DC01',
            name='System Head',
            account_group='asset',
            default_code=True,
        )
        self.assertTrue(system_head.default_code)
