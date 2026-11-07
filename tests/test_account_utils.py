from datetime import date
from decimal import Decimal

from apps.core.account_utils import generate_account_number
from apps.loans.models import LoanAccount, LoanProduct
from apps.savings.models import SavingsAccount

from .base import BaseTestCase


class GenerateAccountNumberTests(BaseTestCase):
    """Tests for account number generation utility.

    Format: SocietyCode(3) + BranchCode(2) + AccountCode(3) + Sequential(7) = 15 chars
    Default society_code = '001', branch HO -> 'HO', account code '2001' -> '200'
    So prefix = '001HO200', first = '001HO2000000001'
    """

    def test_first_account_number(self):
        result = generate_account_number(self.head_office, '2001')
        self.assertEqual(result, '001HO2000000001')
        self.assertEqual(len(result), 15)

    def test_sequential_numbering(self):
        SavingsAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            account_no='001HO2000000001',
            account_type='savings',
            opening_date=date(2024, 1, 1),
            status='active',
        )
        result = generate_account_number(self.head_office, '2001')
        self.assertEqual(result, '001HO2000000002')

    def test_different_branch_codes(self):
        result_ho = generate_account_number(self.head_office, '2001')
        result_br = generate_account_number(self.branch_a, '2001')
        self.assertNotEqual(result_ho, result_br)
        self.assertEqual(len(result_ho), 15)
        self.assertEqual(len(result_br), 15)

    def test_different_account_codes(self):
        result_savings = generate_account_number(self.head_office, '2001')
        result_loans = generate_account_number(self.head_office, '1003')
        self.assertNotEqual(result_savings, result_loans)

    def test_account_number_length(self):
        result = generate_account_number(self.branch_a, '2001')
        self.assertEqual(len(result), 15)

    def test_sequential_across_multiple_accounts(self):
        prefix = '001HO200'
        for i in range(1, 4):
            SavingsAccount.objects.create(
                member=self.member1,
                branch=self.head_office,
                account_no=f'{prefix}{i:07d}',
                account_type='savings',
                opening_date=date(2024, 1, 1),
                status='active',
            )
        result = generate_account_number(self.head_office, '2001')
        self.assertEqual(result, '001HO2000000004')

    def test_loan_accounts_included_in_sequence(self):
        product = LoanProduct.objects.create(
            name='Test',
            interest_rate=Decimal('12.00'),
            max_amount=Decimal('500000.00'),
            max_tenure_months=60,
            is_active=True,
        )
        prefix = '001HO100'
        LoanAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            loan_product=product,
            loan_no=f'{prefix}0000001',
            applied_date=date(2024, 1, 1),
            applied_amount=Decimal('100000.00'),
            interest_rate=Decimal('12.00'),
            tenure_months=12,
            status='applied',
        )
        result = generate_account_number(self.head_office, '1003')
        self.assertEqual(result, '001HO1000000002')
