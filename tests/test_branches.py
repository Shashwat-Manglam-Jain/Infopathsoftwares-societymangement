from datetime import date
from decimal import Decimal

from apps.accounting.models import ChartOfAccounts
from apps.branches.models import Branch
from apps.savings.models import SavingsAccount
from apps.savings.services import deposit

from .base import BaseTestCase


class BranchCreationTests(BaseTestCase):
    """Tests for branch management."""

    def test_create_branch(self):
        """A branch stores all fields correctly."""
        branch = Branch.objects.create(
            branch_code='BR02',
            branch_name='Branch B',
            address='10 Station Road',
            city='Kolhapur',
            state='Maharashtra',
            pincode='416001',
            is_head_office=False,
            status='active',
            opening_date=date(2024, 6, 1),
        )
        self.assertEqual(branch.branch_code, 'BR02')
        self.assertEqual(branch.branch_name, 'Branch B')
        self.assertFalse(branch.is_head_office)

    def test_head_office_exists(self):
        """At least one branch should be marked as head office."""
        ho = Branch.objects.filter(is_head_office=True)
        self.assertEqual(ho.count(), 1)
        self.assertEqual(ho.first(), self.head_office)

    def test_branch_str(self):
        """String representation includes name and HO suffix."""
        expected = 'Head Office (HO)'
        self.assertEqual(str(self.head_office), expected)

    def test_branch_status_change(self):
        """A branch can be deactivated."""
        self.branch_a.status = 'inactive'
        self.branch_a.save()
        self.branch_a.refresh_from_db()
        self.assertEqual(self.branch_a.status, 'inactive')


class BranchSwitchingTests(BaseTestCase):
    """Tests for branch switching in sessions."""

    def test_switch_branch_in_session(self):
        """User can switch their active branch via session."""
        self.client.login(username='admin', password='testpass123')
        session = self.client.session
        session['current_branch_id'] = self.branch_a.pk
        session.save()

        self.assertEqual(
            self.client.session['current_branch_id'],
            self.branch_a.pk,
        )

    def test_default_branch_is_head_office(self):
        """When no branch is selected, head office is the default.

        This is enforced by middleware, but we verify the concept here.
        """
        ho = Branch.objects.filter(is_head_office=True).first()
        self.assertIsNotNone(ho)
        self.assertEqual(ho, self.head_office)


class BranchDataIsolationTests(BaseTestCase):
    """Tests for branch-level data isolation."""

    def setUp(self):
        super().setUp()
        self._setup_coa()

    def _setup_coa(self):
        ChartOfAccounts.objects.create(
            code='1001',
            name='Cash - HO',
            account_group='asset',
            account_type='cash',
            is_system=True,
            branch=self.head_office,
        )
        ChartOfAccounts.objects.create(
            code='1002',
            name='Cash - BR01',
            account_group='asset',
            account_type='cash',
            is_system=True,
            branch=self.branch_a,
        )
        ChartOfAccounts.objects.create(
            code='2001',
            name='Savings Deposits',
            account_group='liability',
            account_type='deposits_taken',
            is_system=True,
        )

    def test_branch_data_isolation(self):
        """Filtering by branch returns only that branch's data."""
        acc_ho = SavingsAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            account_type='savings',
            opening_date=date(2024, 1, 1),
            status='active',
            interest_rate=Decimal('6.00'),
            created_by=self.cashier_user,
        )
        acc_br = SavingsAccount.objects.create(
            member=self.member2,
            branch=self.branch_a,
            account_type='savings',
            opening_date=date(2024, 1, 1),
            status='active',
            interest_rate=Decimal('6.00'),
            created_by=self.branch_cashier,
        )

        ho_accounts = SavingsAccount.objects.filter(branch=self.head_office)
        br_accounts = SavingsAccount.objects.filter(branch=self.branch_a)

        self.assertEqual(ho_accounts.count(), 1)
        self.assertEqual(br_accounts.count(), 1)
        self.assertIn(acc_ho, ho_accounts)
        self.assertNotIn(acc_br, ho_accounts)

    def test_inter_branch_transaction(self):
        """A member from branch A can transact at head office."""
        acc = SavingsAccount.objects.create(
            member=self.member2,  # branch A member
            branch=self.branch_a,
            account_type='savings',
            opening_date=date(2024, 1, 1),
            status='active',
            interest_rate=Decimal('6.00'),
            created_by=self.branch_cashier,
        )
        txn = deposit(
            account=acc,
            amount=Decimal('5000.00'),
            branch=self.head_office,  # transacting at different branch
            user=self.cashier_user,
            payment_mode='cash',
            narration='Inter-branch deposit',
        )
        # Transaction recorded against HO branch
        self.assertEqual(txn.branch, self.head_office)
        # But account still belongs to branch A
        acc.refresh_from_db()
        self.assertEqual(acc.branch, self.branch_a)
        self.assertEqual(acc.current_balance, Decimal('5000.00'))
