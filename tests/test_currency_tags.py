from decimal import Decimal

from django.test import TestCase

from apps.dashboard.templatetags.currency_tags import indian_currency, short_currency


class IndianCurrencyTests(TestCase):
    """Tests for the indian_currency template filter."""

    def test_zero(self):
        self.assertEqual(indian_currency(0), '₹0.00')

    def test_none(self):
        self.assertEqual(indian_currency(None), '₹0.00')

    def test_small_number(self):
        self.assertEqual(indian_currency(Decimal('123.45')), '₹123.45')

    def test_thousands(self):
        self.assertEqual(indian_currency(Decimal('1234.56')), '₹1,234.56')

    def test_lakhs(self):
        self.assertEqual(indian_currency(Decimal('123456.78')), '₹1,23,456.78')

    def test_crores(self):
        self.assertEqual(indian_currency(Decimal('12345678.90')), '₹1,23,45,678.90')

    def test_ten_crores(self):
        self.assertEqual(indian_currency(Decimal('123456789.00')), '₹12,34,56,789.00')

    def test_negative_value(self):
        result = indian_currency(Decimal('-50000.00'))
        self.assertTrue(result.startswith('-₹'))
        self.assertIn('50,000.00', result)

    def test_integer_input(self):
        self.assertEqual(indian_currency(1000), '₹1,000.00')

    def test_string_input(self):
        self.assertEqual(indian_currency('5000.50'), '₹5,000.50')

    def test_invalid_input(self):
        result = indian_currency('not_a_number')
        self.assertEqual(result, 'not_a_number')

    def test_exact_hundred(self):
        self.assertEqual(indian_currency(Decimal('100')), '₹100.00')

    def test_one_rupee(self):
        self.assertEqual(indian_currency(Decimal('1')), '₹1.00')

    def test_paise_only(self):
        self.assertEqual(indian_currency(Decimal('0.50')), '₹0.50')


class ShortCurrencyTests(TestCase):
    """Tests for the short_currency template filter."""

    def test_zero(self):
        self.assertEqual(short_currency(0), '₹0')

    def test_none(self):
        self.assertEqual(short_currency(None), '₹0')

    def test_hundreds(self):
        self.assertEqual(short_currency(Decimal('500')), '₹500')

    def test_thousands(self):
        result = short_currency(Decimal('45000'))
        self.assertEqual(result, '₹45.0K')

    def test_lakhs(self):
        result = short_currency(Decimal('120000'))
        self.assertEqual(result, '₹1.2L')

    def test_crores(self):
        result = short_currency(Decimal('35000000'))
        self.assertEqual(result, '₹3.5Cr')

    def test_exact_lakh(self):
        result = short_currency(Decimal('100000'))
        self.assertEqual(result, '₹1.0L')

    def test_exact_crore(self):
        result = short_currency(Decimal('10000000'))
        self.assertEqual(result, '₹1.0Cr')

    def test_small_number(self):
        self.assertEqual(short_currency(Decimal('50')), '₹50')

    def test_invalid_input(self):
        result = short_currency('abc')
        self.assertEqual(result, 'abc')
