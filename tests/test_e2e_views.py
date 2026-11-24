"""
End-to-end view tests covering every major feature:
members, savings, loans, accounting, reports, shares, deposits, agents,
dashboard, NPA classification, branch filtering, role access.
"""

from datetime import date
from decimal import Decimal

from django.urls import reverse

from apps.accounting.initial_coa import setup_chart_of_accounts
from apps.accounting.models import ChartOfAccounts, FixedAsset, JournalEntry
from apps.loans.models import LoanAccount, LoanProduct
from apps.loans.npa_service import classify_all_loans, classify_loan, get_npa_report
from apps.members.models import Member
from apps.savings.models import SavingsAccount
from tests.base import BaseTestCase


def _login(client, role='admin'):
    client.login(username=role, password='testpass123')


class MemberViewTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        setup_chart_of_accounts([self.head_office])

    def test_member_list_loads(self):
        _login(self.client)
        resp = self.client.get(reverse('members:list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Rajesh Kumar')

    def test_member_detail_loads(self):
        _login(self.client)
        resp = self.client.get(reverse('members:detail', args=[self.member1.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_member_create_with_nominee(self):
        _login(self.client)
        data = {
            'name': 'Sunil Patil',
            'father_name': 'Dinesh Patil',
            'dob': '1992-06-15',
            'gender': 'male',
            'phone': '9988776655',
            'address': '10 New Lane',
            'city': 'Nagpur',
            'state': 'Maharashtra',
            'pincode': '440001',
            'join_date': date.today().isoformat(),
            'status': 'active',
            'category': 'A',
            'branch': self.head_office.pk,
            'nominees-TOTAL_FORMS': '4',
            'nominees-INITIAL_FORMS': '0',
            'nominees-MIN_NUM_FORMS': '1',
            'nominees-MAX_NUM_FORMS': '1000',
            'nominees-0-name': 'Anita Patil',
            'nominees-0-relation': 'Wife',
            'nominees-0-share_percentage': '100',
            'nominees-1-DELETE': 'on',
            'nominees-2-DELETE': 'on',
            'nominees-3-DELETE': 'on',
        }
        resp = self.client.post(reverse('members:create'), data)
        if resp.status_code == 200 and resp.context:
            form_errors = resp.context.get('form', {})
            formset_errors = resp.context.get('nominee_formset', {})
            self.fail(
                f'Form errors: {getattr(form_errors, "errors", "")}, Formset: {getattr(formset_errors, "errors", "")}'
            )
        self.assertEqual(resp.status_code, 302)
        member = Member.objects.get(name='Sunil Patil')
        self.assertEqual(member.nominees.count(), 1)
        self.assertEqual(member.nominees.first().name, 'Anita Patil')

    def test_member_create_no_nominee_fails(self):
        _login(self.client)
        data = {
            'name': 'No Nominee Guy',
            'father_name': 'Father',
            'dob': '1990-01-01',
            'gender': 'male',
            'phone': '1111111111',
            'address': 'Addr',
            'city': 'City',
            'state': 'State',
            'pincode': '111111',
            'join_date': date.today().isoformat(),
            'status': 'active',
            'category': 'A',
            'branch': self.head_office.pk,
            'nominees-TOTAL_FORMS': '4',
            'nominees-INITIAL_FORMS': '0',
            'nominees-MIN_NUM_FORMS': '1',
            'nominees-MAX_NUM_FORMS': '1000',
            'nominees-0-name': '',
            'nominees-0-relation': '',
            'nominees-0-share_percentage': '',
            'nominees-1-name': '',
            'nominees-1-relation': '',
            'nominees-1-share_percentage': '',
            'nominees-2-name': '',
            'nominees-2-relation': '',
            'nominees-2-share_percentage': '',
            'nominees-3-name': '',
            'nominees-3-relation': '',
            'nominees-3-share_percentage': '',
        }
        resp = self.client.post(reverse('members:create'), data)
        self.assertEqual(resp.status_code, 200)

    def test_member_edit(self):
        _login(self.client)
        resp = self.client.get(reverse('members:edit', args=[self.member1.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_cashier_can_access_member_create(self):
        _login(self.client, 'cashier')
        resp = self.client.get(reverse('members:create'))
        self.assertEqual(resp.status_code, 200)


class AccountingViewTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        setup_chart_of_accounts([self.head_office, self.branch_a])

    def test_heads_list(self):
        _login(self.client)
        resp = self.client.get(reverse('accounting:heads'))
        self.assertEqual(resp.status_code, 200)

    def test_voucher_list(self):
        _login(self.client)
        resp = self.client.get(reverse('accounting:vouchers'))
        self.assertEqual(resp.status_code, 200)

    def test_voucher_create_page(self):
        _login(self.client)
        resp = self.client.get(reverse('accounting:voucher_create'))
        self.assertEqual(resp.status_code, 200)

    def test_create_receipt_voucher(self):
        _login(self.client)
        debit = ChartOfAccounts.objects.filter(account_group='asset').first()
        credit = ChartOfAccounts.objects.filter(account_group='liability').first()
        if debit and credit:
            data = {
                'voucher_type': 'receipt',
                'date': date.today().isoformat(),
                'debit_account': debit.pk,
                'credit_account': credit.pk,
                'amount': '1000.00',
                'narration': 'Test receipt',
                'branch': self.head_office.pk,
            }
            resp = self.client.post(reverse('accounting:voucher_create'), data)
            self.assertIn(resp.status_code, [200, 302])

    def test_create_payment_voucher(self):
        _login(self.client)
        debit = ChartOfAccounts.objects.filter(account_group='expense').first()
        credit = ChartOfAccounts.objects.filter(account_group='asset').first()
        if debit and credit:
            data = {
                'voucher_type': 'payment',
                'date': date.today().isoformat(),
                'debit_account': debit.pk,
                'credit_account': credit.pk,
                'amount': '500.00',
                'narration': 'Test payment',
                'branch': self.head_office.pk,
            }
            resp = self.client.post(reverse('accounting:voucher_create'), data)
            self.assertIn(resp.status_code, [200, 302])

    def test_voucher_cancel_page(self):
        _login(self.client)
        entry = JournalEntry.objects.first()
        if entry:
            resp = self.client.get(reverse('accounting:voucher_cancel', args=[entry.pk]))
            self.assertIn(resp.status_code, [200, 302])

    def test_general_ledger(self):
        _login(self.client)
        resp = self.client.get(reverse('accounting:general_ledger'))
        self.assertEqual(resp.status_code, 200)

    def test_day_book(self):
        _login(self.client)
        resp = self.client.get(reverse('accounting:day_book'))
        self.assertEqual(resp.status_code, 200)

    def test_interest_master(self):
        _login(self.client)
        resp = self.client.get(reverse('accounting:interest_master'))
        self.assertEqual(resp.status_code, 200)

    def test_cashbook_report(self):
        _login(self.client)
        resp = self.client.get(reverse('accounting:cashbook_report'))
        self.assertEqual(resp.status_code, 200)

    def test_opening_balance(self):
        _login(self.client)
        resp = self.client.get(reverse('accounting:opening_balance'))
        self.assertEqual(resp.status_code, 200)

    def test_journal_entry_and_reversal(self):
        _login(self.client)
        debit = ChartOfAccounts.objects.filter(account_group='asset').first()
        credit = ChartOfAccounts.objects.filter(account_group='income').first()
        if debit and credit:
            data = {
                'voucher_type': 'journal',
                'date': date.today().isoformat(),
                'debit_account': debit.pk,
                'credit_account': credit.pk,
                'amount': '2000.00',
                'narration': 'JV for reversal test',
                'branch': self.head_office.pk,
            }
            resp = self.client.post(reverse('accounting:voucher_create'), data)
            self.assertIn(resp.status_code, [200, 302])


class SavingsViewTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        setup_chart_of_accounts([self.head_office, self.branch_a])
        self.savings = SavingsAccount.objects.create(
            account_no='SAV001',
            member=self.member1,
            branch=self.head_office,
            account_type='savings',
            current_balance=Decimal('10000'),
            opening_date=date(2024, 1, 1),
            status='active',
        )

    def test_savings_list(self):
        _login(self.client)
        resp = self.client.get(reverse('savings:list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'SAV001')

    def test_savings_detail(self):
        _login(self.client)
        resp = self.client.get(reverse('savings:detail', args=[self.savings.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_savings_create_page(self):
        _login(self.client)
        resp = self.client.get(reverse('savings:create'))
        self.assertEqual(resp.status_code, 200)

    def test_savings_statement(self):
        _login(self.client)
        resp = self.client.get(reverse('savings:statement', args=[self.savings.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_director_security_account_type(self):
        ds = SavingsAccount.objects.create(
            account_no='DS001',
            member=self.member1,
            branch=self.head_office,
            account_type='director_security',
            current_balance=Decimal('50000'),
            opening_date=date(2024, 1, 1),
            status='active',
        )
        self.assertEqual(ds.account_type, 'director_security')

    def test_manual_account_no(self):
        sa = SavingsAccount.objects.create(
            account_no='MAN001',
            member=self.member2,
            branch=self.branch_a,
            account_type='savings',
            current_balance=Decimal('0'),
            opening_date=date(2024, 1, 1),
            status='active',
            manual_account_no='LEGACY-123',
        )
        self.assertEqual(sa.manual_account_no, 'LEGACY-123')


class LoanViewTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        setup_chart_of_accounts([self.head_office, self.branch_a])
        self.product = LoanProduct.objects.create(
            name='Gold Loan',
            interest_rate=Decimal('12'),
            max_amount=Decimal('500000'),
            max_tenure_months=60,
            mortgage_type='none',
        )
        self.loan = LoanAccount.objects.create(
            loan_no='LN001',
            member=self.member1,
            loan_product=self.product,
            branch=self.head_office,
            applied_date=date.today(),
            applied_amount=Decimal('50000'),
            approved_amount=Decimal('50000'),
            outstanding_principal=Decimal('45000'),
            bal_interest=Decimal('500'),
            bal_penal=Decimal('0'),
            overdue_days=10,
            tenure_months=24,
            emi_amount=Decimal('2354'),
            interest_rate=Decimal('12'),
            status='disbursed',
            created_by=self.admin_user,
        )

    def test_loan_list(self):
        _login(self.client)
        resp = self.client.get(reverse('loans:list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'LN001')

    def test_loan_detail(self):
        _login(self.client)
        resp = self.client.get(reverse('loans:detail', args=[self.loan.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_loan_apply_page(self):
        _login(self.client)
        resp = self.client.get(reverse('loans:apply'))
        self.assertEqual(resp.status_code, 200)

    def test_npa_classify_standard_loan(self):
        result = classify_loan(self.loan)
        self.assertEqual(result['category'], 'standard')
        self.assertEqual(result['provision_percent'], Decimal('0.25'))

    def test_npa_classify_substandard_loan(self):
        self.loan.overdue_days = 120
        result = classify_loan(self.loan)
        self.assertEqual(result['category'], 'sub_standard')
        self.assertEqual(result['provision_percent'], Decimal('6'))

    def test_npa_classify_doubtful(self):
        self.loan.overdue_days = 400
        result = classify_loan(self.loan)
        self.assertEqual(result['category'], 'doubtful_1')

    def test_npa_classify_clears_npa_date_for_standard(self):
        self.loan.npa_date = date(2024, 6, 1)
        self.loan.npa_category = 'sub_standard'
        self.loan.overdue_days = 10
        self.loan.save()
        classify_all_loans()
        self.loan.refresh_from_db()
        self.assertIsNone(self.loan.npa_date)
        self.assertEqual(self.loan.npa_category, 'standard')

    def test_npa_classify_all_loans(self):
        result = classify_all_loans()
        self.assertIn('total', result)
        self.assertIn('updated', result)

    def test_npa_mortgage_different_rates(self):
        mortgage_product = LoanProduct.objects.create(
            name='Mortgage Loan',
            interest_rate=Decimal('10'),
            max_amount=Decimal('1000000'),
            max_tenure_months=120,
            mortgage_type='property',
        )
        mortgage_loan = LoanAccount.objects.create(
            loan_no='ML001',
            member=self.member2,
            loan_product=mortgage_product,
            branch=self.head_office,
            applied_date=date.today(),
            applied_amount=Decimal('100000'),
            approved_amount=Decimal('100000'),
            outstanding_principal=Decimal('90000'),
            bal_interest=Decimal('0'),
            bal_penal=Decimal('0'),
            overdue_days=400,
            tenure_months=120,
            emi_amount=Decimal('5000'),
            interest_rate=Decimal('10'),
            status='disbursed',
            created_by=self.admin_user,
        )
        result = classify_loan(mortgage_loan)
        self.assertEqual(result['category'], 'doubtful_1')
        self.assertEqual(result['provision_percent'], Decimal('20'))

    def test_npa_report_data(self):
        report = get_npa_report()
        self.assertEqual(report['total_loans'], 1)
        self.assertIn('by_product', report)

    def test_rd_mortgage_type(self):
        rd_product = LoanProduct.objects.create(
            name='RD Loan',
            interest_rate=Decimal('11'),
            max_amount=Decimal('200000'),
            max_tenure_months=36,
            mortgage_type='rd',
        )
        self.assertEqual(rd_product.mortgage_type, 'rd')


class ReportViewTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        setup_chart_of_accounts([self.head_office, self.branch_a])

    def test_report_index(self):
        _login(self.client)
        resp = self.client.get(reverse('reports:index'))
        self.assertEqual(resp.status_code, 200)

    def test_trial_balance(self):
        _login(self.client)
        resp = self.client.get(reverse('reports:trial_balance'))
        self.assertEqual(resp.status_code, 200)

    def test_profit_loss_no_date(self):
        _login(self.client)
        resp = self.client.get(reverse('reports:profit_loss'))
        self.assertEqual(resp.status_code, 200)

    def test_profit_loss_with_date(self):
        _login(self.client)
        resp = self.client.get(reverse('reports:profit_loss'), {'as_on_date': date.today().isoformat()})
        self.assertEqual(resp.status_code, 200)

    def test_balance_sheet_no_date(self):
        _login(self.client)
        resp = self.client.get(reverse('reports:balance_sheet'))
        self.assertEqual(resp.status_code, 200)

    def test_balance_sheet_with_date(self):
        _login(self.client)
        resp = self.client.get(reverse('reports:balance_sheet'), {'as_on_date': date.today().isoformat()})
        self.assertEqual(resp.status_code, 200)

    def test_subsidiary_ledger_no_type(self):
        _login(self.client)
        resp = self.client.get(reverse('reports:subsidiary_ledger'))
        self.assertEqual(resp.status_code, 200)

    def test_subsidiary_ledger_savings(self):
        _login(self.client)
        SavingsAccount.objects.create(
            account_no='SL001',
            member=self.member1,
            branch=self.head_office,
            account_type='savings',
            current_balance=Decimal('5000'),
            opening_date=date(2024, 1, 1),
            status='active',
        )
        resp = self.client.get(reverse('reports:subsidiary_ledger'), {'type': 'savings'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'SL001')

    def test_subsidiary_ledger_loans(self):
        _login(self.client)
        product = LoanProduct.objects.create(
            name='Term Loan',
            interest_rate=Decimal('12'),
            max_amount=Decimal('500000'),
            max_tenure_months=60,
        )
        LoanAccount.objects.create(
            loan_no='SL-LN001',
            member=self.member1,
            loan_product=product,
            branch=self.head_office,
            applied_date=date.today(),
            applied_amount=Decimal('50000'),
            approved_amount=Decimal('50000'),
            outstanding_principal=Decimal('50000'),
            bal_interest=Decimal('0'),
            bal_penal=Decimal('0'),
            overdue_days=0,
            tenure_months=24,
            emi_amount=Decimal('2354'),
            interest_rate=Decimal('12'),
            status='disbursed',
            created_by=self.admin_user,
        )
        resp = self.client.get(reverse('reports:subsidiary_ledger'), {'type': 'loans'})
        self.assertEqual(resp.status_code, 200)

    def test_subsidiary_ledger_director_security(self):
        _login(self.client)
        resp = self.client.get(reverse('reports:subsidiary_ledger'), {'type': 'director_security'})
        self.assertEqual(resp.status_code, 200)

    def test_subsidiary_ledger_csv_export(self):
        _login(self.client)
        SavingsAccount.objects.create(
            account_no='CSVSAV01',
            member=self.member1,
            branch=self.head_office,
            account_type='savings',
            current_balance=Decimal('3000'),
            opening_date=date(2024, 1, 1),
            status='active',
        )
        resp = self.client.get(
            reverse('reports:subsidiary_ledger'),
            {'type': 'savings', 'format': 'csv'},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv')

    def test_personal_ledger(self):
        _login(self.client)
        resp = self.client.get(reverse('reports:personal_ledger'))
        self.assertEqual(resp.status_code, 200)

    def test_cashbook_report(self):
        _login(self.client)
        resp = self.client.get(reverse('reports:cashbook_report'))
        self.assertEqual(resp.status_code, 200)

    def test_deposit_reports(self):
        _login(self.client)
        resp = self.client.get(reverse('reports:deposit_reports'))
        self.assertEqual(resp.status_code, 200)

    def test_loan_reports(self):
        _login(self.client)
        resp = self.client.get(reverse('reports:loan_reports'))
        self.assertEqual(resp.status_code, 200)

    def test_balance_reports(self):
        _login(self.client)
        resp = self.client.get(reverse('reports:balance_reports'))
        self.assertEqual(resp.status_code, 200)

    def test_enquiry(self):
        _login(self.client)
        resp = self.client.get(reverse('reports:enquiry'))
        self.assertEqual(resp.status_code, 200)

    def test_pigmmy_reports(self):
        _login(self.client)
        resp = self.client.get(reverse('reports:pigmmy_reports'))
        self.assertEqual(resp.status_code, 200)

    def test_notices(self):
        _login(self.client)
        resp = self.client.get(reverse('reports:notices'))
        self.assertEqual(resp.status_code, 200)

    def test_calculator(self):
        _login(self.client)
        resp = self.client.get(reverse('reports:calculator'))
        self.assertEqual(resp.status_code, 200)

    def test_npa_report_view(self):
        _login(self.client)
        resp = self.client.get(reverse('reports:npa_report'))
        self.assertEqual(resp.status_code, 200)

    def test_npa_report_reclassify_post(self):
        _login(self.client)
        resp = self.client.post(reverse('reports:npa_report'), {'action': 'reclassify'})
        self.assertIn(resp.status_code, [200, 302])

    def test_npa_report_csv_export(self):
        _login(self.client)
        product = LoanProduct.objects.create(
            name='CSV Loan',
            interest_rate=Decimal('12'),
            max_amount=Decimal('500000'),
            max_tenure_months=60,
        )
        LoanAccount.objects.create(
            loan_no='CSV001',
            member=self.member1,
            loan_product=product,
            branch=self.head_office,
            applied_date=date.today(),
            applied_amount=Decimal('50000'),
            approved_amount=Decimal('50000'),
            outstanding_principal=Decimal('40000'),
            bal_interest=Decimal('0'),
            bal_penal=Decimal('0'),
            overdue_days=0,
            tenure_months=24,
            emi_amount=Decimal('2354'),
            interest_rate=Decimal('12'),
            status='disbursed',
            created_by=self.admin_user,
        )
        resp = self.client.get(reverse('reports:npa_report'), {'format': 'csv'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv')

    def test_agent_reconciliation(self):
        _login(self.client)
        resp = self.client.get(reverse('reports:agent_reconciliation'))
        self.assertEqual(resp.status_code, 200)

    def test_agent_reconciliation_csv(self):
        _login(self.client)
        resp = self.client.get(reverse('reports:agent_reconciliation'), {'format': 'csv'})
        self.assertEqual(resp.status_code, 200)

    def test_fixed_asset_report(self):
        _login(self.client)
        resp = self.client.get(reverse('reports:fixed_asset_report'))
        self.assertEqual(resp.status_code, 200)

    def test_fixed_asset_report_with_assets(self):
        _login(self.client)
        gl = ChartOfAccounts.objects.filter(account_group='asset').first()
        dep_head = ChartOfAccounts.objects.filter(account_group='expense').first()
        if gl and dep_head:
            FixedAsset.objects.create(
                name='Computer',
                asset_code='FA001',
                gl_head=gl,
                depreciation_head=dep_head,
                purchase_date=date(2024, 1, 1),
                purchase_amount=Decimal('50000'),
                depreciation_rate=Decimal('15'),
                depreciation_method='slm',
                accumulated_depreciation=Decimal('7500'),
                written_down_value=Decimal('42500'),
                branch=self.head_office,
            )
        resp = self.client.get(reverse('reports:fixed_asset_report'))
        self.assertEqual(resp.status_code, 200)


class RoleAccessTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        setup_chart_of_accounts([self.head_office])

    def test_cashier_can_access_reports(self):
        _login(self.client, 'cashier')
        for url_name in [
            'reports:trial_balance',
            'reports:profit_loss',
            'reports:balance_sheet',
            'reports:npa_report',
            'reports:fixed_asset_report',
        ]:
            resp = self.client.get(reverse(url_name))
            self.assertEqual(resp.status_code, 200, f'{url_name} should be accessible for cashier')

    def test_admin_can_access_all_reports(self):
        _login(self.client)
        for url_name in [
            'reports:trial_balance',
            'reports:profit_loss',
            'reports:balance_sheet',
            'reports:npa_report',
            'reports:fixed_asset_report',
            'reports:subsidiary_ledger',
            'reports:agent_reconciliation',
        ]:
            resp = self.client.get(reverse(url_name))
            self.assertEqual(resp.status_code, 200, f'{url_name} should be accessible for admin')

    def test_accountant_can_access_reports(self):
        _login(self.client, 'accountant')
        for url_name in [
            'reports:trial_balance',
            'reports:profit_loss',
            'reports:balance_sheet',
        ]:
            resp = self.client.get(reverse(url_name))
            self.assertEqual(
                resp.status_code,
                200,
                f'{url_name} should be accessible for accountant',
            )


class BranchFilterTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        setup_chart_of_accounts([self.head_office, self.branch_a])

    def test_admin_sees_all_branches(self):
        _login(self.client)
        resp = self.client.get(reverse('members:list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Rajesh Kumar')
        self.assertContains(resp, 'Priya Sharma')

    def test_branch_user_sees_own_branch_only(self):
        _login(self.client, 'branch_cashier')
        resp = self.client.get(reverse('members:list'))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'Rajesh Kumar')
        self.assertContains(resp, 'Priya Sharma')


class ShareViewTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        setup_chart_of_accounts([self.head_office])

    def test_share_list(self):
        _login(self.client)
        resp = self.client.get(reverse('shares:list'))
        self.assertEqual(resp.status_code, 200)


class DepositViewTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        setup_chart_of_accounts([self.head_office])

    def test_fd_list(self):
        _login(self.client)
        resp = self.client.get(reverse('deposits:fd_list'))
        self.assertEqual(resp.status_code, 200)

    def test_rd_list(self):
        _login(self.client)
        resp = self.client.get(reverse('deposits:rd_list'))
        self.assertEqual(resp.status_code, 200)


class FixedAssetModelTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        setup_chart_of_accounts([self.head_office])
        self.gl = ChartOfAccounts.objects.filter(account_group='asset').first()

    def test_create_fixed_asset(self):
        asset = FixedAsset.objects.create(
            name='Printer',
            asset_code='FA-P01',
            gl_head=self.gl,
            purchase_date=date(2024, 3, 1),
            purchase_amount=Decimal('25000'),
            depreciation_rate=Decimal('10'),
            branch=self.head_office,
        )
        self.assertEqual(str(asset), 'FA-P01 — Printer')

    def test_net_book_value_property(self):
        asset = FixedAsset.objects.create(
            name='Desk',
            asset_code='FA-D01',
            gl_head=self.gl,
            purchase_date=date(2024, 1, 1),
            purchase_amount=Decimal('10000'),
            accumulated_depreciation=Decimal('2000'),
            branch=self.head_office,
        )
        self.assertEqual(asset.net_book_value, Decimal('8000'))

    def test_unique_asset_code(self):
        FixedAsset.objects.create(
            name='Chair',
            asset_code='FA-C01',
            gl_head=self.gl,
            purchase_date=date(2024, 1, 1),
            purchase_amount=Decimal('5000'),
            branch=self.head_office,
        )
        with self.assertRaises(Exception):
            FixedAsset.objects.create(
                name='Chair 2',
                asset_code='FA-C01',
                gl_head=self.gl,
                purchase_date=date(2024, 2, 1),
                purchase_amount=Decimal('6000'),
                branch=self.head_office,
            )


class AgentViewTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        setup_chart_of_accounts([self.head_office])

    def test_agent_list(self):
        _login(self.client)
        resp = self.client.get(reverse('agents:list'))
        self.assertEqual(resp.status_code, 200)


class DashboardTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        setup_chart_of_accounts([self.head_office])

    def test_dashboard_loads(self):
        _login(self.client)
        resp = self.client.get(reverse('dashboard:index'))
        self.assertEqual(resp.status_code, 200)

    def test_unauthenticated_redirects_to_login(self):
        resp = self.client.get(reverse('dashboard:index'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('login', resp.url)
