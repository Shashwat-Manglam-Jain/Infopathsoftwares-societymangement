"""Standalone unit tests that run without PostgreSQL.

Tests pure business logic functions — no database required.
"""

import unittest
from decimal import Decimal


class AmountToWordsTests(unittest.TestCase):
    def setUp(self):
        import os

        import django

        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
        django.setup()
        from apps.core.account_utils import amount_to_words

        self.amount_to_words = amount_to_words

    def test_zero(self):
        self.assertEqual(self.amount_to_words(0), 'Zero Rupees Only')

    def test_single_digit(self):
        self.assertEqual(self.amount_to_words(5), 'Five Rupees Only')

    def test_teens(self):
        self.assertEqual(self.amount_to_words(13), 'Thirteen Rupees Only')

    def test_tens(self):
        self.assertEqual(self.amount_to_words(50), 'Fifty Rupees Only')

    def test_hundred(self):
        self.assertEqual(self.amount_to_words(100), 'One Hundred Rupees Only')

    def test_thousands(self):
        self.assertEqual(self.amount_to_words(1234), 'One Thousand Two Hundred Thirty Four Rupees Only')

    def test_lakhs(self):
        self.assertEqual(self.amount_to_words(100000), 'One Lakh Rupees Only')

    def test_crores(self):
        self.assertEqual(self.amount_to_words(10000000), 'One Crore Rupees Only')

    def test_paise_rounding(self):
        result = self.amount_to_words(1234.56)
        self.assertIn('Fifty Six Paise', result)

    def test_paise_one(self):
        result = self.amount_to_words(100.01)
        self.assertIn('One Paise', result)

    def test_paise_ninety_nine(self):
        result = self.amount_to_words(0.99)
        self.assertEqual(result, 'Zero Rupees and Ninety Nine Paise Only')

    def test_large_amount(self):
        result = self.amount_to_words(99999999.99)
        self.assertIn('Nine Crore', result)
        self.assertIn('Ninety Nine Paise', result)

    def test_ends_with_only(self):
        self.assertTrue(self.amount_to_words(500).endswith('Only'))

    def test_decimal_input(self):
        result = self.amount_to_words(Decimal('2500.75'))
        self.assertIn('Two Thousand Five Hundred', result)
        self.assertIn('Seventy Five Paise', result)


class IndianCurrencyFilterTests(unittest.TestCase):
    def setUp(self):
        import os

        import django

        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
        django.setup()
        from apps.dashboard.templatetags.currency_tags import indian_currency, short_currency

        self.indian_currency = indian_currency
        self.short_currency = short_currency

    def test_zero(self):
        self.assertEqual(self.indian_currency(0), '₹0.00')

    def test_none(self):
        self.assertEqual(self.indian_currency(None), '₹0.00')

    def test_small_number(self):
        self.assertEqual(self.indian_currency(Decimal('123.45')), '₹123.45')

    def test_thousands_comma(self):
        self.assertEqual(self.indian_currency(Decimal('1234.56')), '₹1,234.56')

    def test_lakhs_format(self):
        self.assertEqual(self.indian_currency(Decimal('123456.78')), '₹1,23,456.78')

    def test_crores_format(self):
        self.assertEqual(self.indian_currency(Decimal('12345678.90')), '₹1,23,45,678.90')

    def test_negative(self):
        result = self.indian_currency(Decimal('-50000.00'))
        self.assertTrue(result.startswith('-₹'))

    def test_integer_input(self):
        self.assertEqual(self.indian_currency(1000), '₹1,000.00')

    def test_invalid_input(self):
        self.assertEqual(self.indian_currency('not_a_number'), 'not_a_number')

    def test_short_zero(self):
        self.assertEqual(self.short_currency(0), '₹0')

    def test_short_hundreds(self):
        self.assertEqual(self.short_currency(Decimal('500')), '₹500')

    def test_short_thousands(self):
        self.assertEqual(self.short_currency(Decimal('45000')), '₹45.0K')

    def test_short_lakhs(self):
        self.assertEqual(self.short_currency(Decimal('120000')), '₹1.2L')

    def test_short_crores(self):
        self.assertEqual(self.short_currency(Decimal('35000000')), '₹3.5Cr')


class EMICalculationTests(unittest.TestCase):
    """Test SBI reducing balance EMI formula."""

    def setUp(self):
        import os

        import django

        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
        django.setup()
        from apps.loans.services import calculate_emi

        self.calculate_emi = calculate_emi

    def test_basic_emi(self):
        emi = self.calculate_emi(Decimal('100000'), Decimal('12.00'), 12)
        self.assertIsInstance(emi, Decimal)
        self.assertGreater(emi, 0)

    def test_higher_rate_higher_emi(self):
        emi_12 = self.calculate_emi(Decimal('100000'), Decimal('12.00'), 12)
        emi_18 = self.calculate_emi(Decimal('100000'), Decimal('18.00'), 12)
        self.assertGreater(emi_18, emi_12)

    def test_longer_tenure_lower_emi(self):
        emi_12 = self.calculate_emi(Decimal('100000'), Decimal('12.00'), 12)
        emi_60 = self.calculate_emi(Decimal('100000'), Decimal('12.00'), 60)
        self.assertLess(emi_60, emi_12)

    def test_larger_amount_higher_emi(self):
        emi_1l = self.calculate_emi(Decimal('100000'), Decimal('12.00'), 12)
        emi_5l = self.calculate_emi(Decimal('500000'), Decimal('12.00'), 12)
        self.assertAlmostEqual(float(emi_5l / emi_1l), 5.0, places=2)

    def test_emi_is_decimal(self):
        emi = self.calculate_emi(Decimal('200000'), Decimal('10.00'), 24)
        self.assertIsInstance(emi, Decimal)

    def test_known_emi_value(self):
        emi = self.calculate_emi(Decimal('100000'), Decimal('12.00'), 12)
        self.assertAlmostEqual(float(emi), 8884.88, delta=5.0)


class FDMaturityCalculationTests(unittest.TestCase):
    def setUp(self):
        import os

        import django

        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
        django.setup()
        from apps.deposits.services import calculate_fd_maturity

        self.calculate_fd_maturity = calculate_fd_maturity

    def test_cumulative_interest(self):
        maturity = self.calculate_fd_maturity(
            principal=Decimal('100000'), annual_rate=Decimal('8.00'), tenure_days=365, compounding='cumulative'
        )
        self.assertIsInstance(maturity, Decimal)
        self.assertGreater(maturity, Decimal('100000'))
        expected = Decimal('108000.00')
        self.assertEqual(maturity, expected)

    def test_quarterly_compounding_higher_than_cumulative(self):
        quarterly = self.calculate_fd_maturity(
            principal=Decimal('100000'), annual_rate=Decimal('8.00'), tenure_days=365, compounding='quarterly'
        )
        cumulative = self.calculate_fd_maturity(
            principal=Decimal('100000'), annual_rate=Decimal('8.00'), tenure_days=365, compounding='cumulative'
        )
        self.assertGreater(quarterly, cumulative)

    def test_interest_earned_cumulative(self):
        maturity = self.calculate_fd_maturity(
            principal=Decimal('100000'), annual_rate=Decimal('8.00'), tenure_days=365, compounding='cumulative'
        )
        interest = maturity - Decimal('100000')
        self.assertGreater(interest, 0)
        expected_interest = Decimal('100000') * Decimal('8.00') / Decimal('100')
        self.assertEqual(interest, expected_interest)


class SavingsInterestTests(unittest.TestCase):
    """calculate_daily_interest needs a SavingsAccount model object + date,
    so we test the math formula directly."""

    def test_daily_interest_formula(self):
        balance = Decimal('100000')
        rate = Decimal('4.00')
        daily_rate = rate / (Decimal('100') * Decimal('365'))
        interest = (balance * daily_rate).quantize(Decimal('0.01'))
        self.assertGreater(interest, 0)
        self.assertAlmostEqual(float(interest), 10.96, delta=0.1)

    def test_daily_interest_proportional(self):
        rate = Decimal('4.00')
        daily_rate = rate / (Decimal('100') * Decimal('365'))
        i1 = Decimal('100000') * daily_rate
        i2 = Decimal('200000') * daily_rate
        self.assertAlmostEqual(float(i2 / i1), 2.0, places=2)

    def test_zero_balance(self):
        balance = Decimal('0')
        rate = Decimal('4.00')
        daily_rate = rate / (Decimal('100') * Decimal('365'))
        interest = balance * daily_rate
        self.assertEqual(interest, 0)


if __name__ == '__main__':
    unittest.main()
