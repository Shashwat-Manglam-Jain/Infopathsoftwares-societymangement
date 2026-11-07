from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone
from django_tenants.utils import tenant_context

from apps.tenants.models import Society


class Command(BaseCommand):
    help = 'Seed realistic test data into a tenant for manual testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--schema',
            type=str,
            default='demo',
            help='Schema name of the tenant to seed (default: demo)',
        )

    def handle(self, *args, **options):
        schema = options['schema']
        try:
            society = Society.objects.get(schema_name=schema)
        except Society.DoesNotExist:
            self.stderr.write(self.style.ERROR(f'Tenant "{schema}" not found. Run create_demo_tenant first.'))
            return

        with tenant_context(society):
            self._seed_branches()
            self._seed_users()
            self._seed_members()
            self._seed_enhanced_member_fields()
            self._seed_share_config()
            self._seed_shares()
            self._seed_loan_products()
            self._seed_fd_products()
            self._seed_savings_accounts()
            self._seed_savings_transactions()
            self._seed_loans()
            self._seed_fixed_deposits()
            self._seed_recurring_deposits()
            self._seed_agents()
            self._seed_working_day()

        self.stdout.write(self.style.SUCCESS('Test data seeded successfully!'))
        self._print_summary()

    def _seed_branches(self):
        from apps.branches.models import Branch

        self.ho = Branch.objects.filter(is_head_office=True).first()
        if not self.ho:
            self.ho = Branch.objects.create(
                branch_code='HO',
                branch_name='Head Office',
                address='123 Main Road',
                city='Pune',
                state='Maharashtra',
                pincode='411001',
                phone='9876543210',
                is_head_office=True,
                opening_date=date(2020, 1, 1),
                status='active',
            )

        self.branch1, _ = Branch.objects.get_or_create(
            branch_code='BR01',
            defaults={
                'branch_name': 'Kothrud Branch',
                'address': '45 Karve Road, Kothrud',
                'city': 'Pune',
                'state': 'Maharashtra',
                'pincode': '411038',
                'phone': '9876543211',
                'is_head_office': False,
                'opening_date': date(2021, 6, 1),
                'status': 'active',
            },
        )

        self.branch2, _ = Branch.objects.get_or_create(
            branch_code='BR02',
            defaults={
                'branch_name': 'Hadapsar Branch',
                'address': '78 Magarpatta Road, Hadapsar',
                'city': 'Pune',
                'state': 'Maharashtra',
                'pincode': '411028',
                'phone': '9876543212',
                'is_head_office': False,
                'opening_date': date(2022, 1, 15),
                'status': 'active',
            },
        )
        self.stdout.write('  Branches: 3 (HO + 2 sub-branches)')

    def _seed_users(self):
        from apps.accounts.models import CustomUser

        self.admin = CustomUser.objects.filter(username='admin').first()

        users_data = [
            ('manager_ho', 'Manager HO', 'branch_manager', self.ho, True),
            ('cashier_ho', 'Cashier HO', 'cashier', self.ho, False),
            ('accountant', 'Accountant', 'accountant', self.ho, True),
            ('manager_br1', 'Manager BR01', 'branch_manager', self.branch1, False),
            ('cashier_br1', 'Cashier BR01', 'cashier', self.branch1, False),
            ('manager_br2', 'Manager BR02', 'branch_manager', self.branch2, False),
            ('cashier_br2', 'Cashier BR02', 'cashier', self.branch2, False),
            ('auditor', 'Auditor', 'auditor', self.ho, True),
        ]

        self.users = {}
        for username, name, role, branch, all_branches in users_data:
            user, created = CustomUser.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': name.split()[0],
                    'last_name': name.split()[-1] if len(name.split()) > 1 else '',
                    'email': f'{username}@demo-society.com',
                    'phone': '9800000000',
                    'role': role,
                    'branch': branch,
                    'can_access_all_branches': all_branches,
                },
            )
            if created:
                user.set_password('test123')
                user.save()
            self.users[username] = user

        self.stdout.write('  Users: 8 (admin + manager/cashier per branch + accountant + auditor)')

    def _seed_members(self):
        from apps.members.models import Member, MemberNominee

        self.members = []
        members_data = [
            ('M0001', self.ho, 'Rajesh Kumar Sharma', 'Suresh Sharma', '1985-05-15', 'M', '9876500001', 'A'),
            ('M0002', self.ho, 'Priya Deshpande', 'Anil Deshpande', '1990-08-20', 'F', '9876500002', 'A'),
            ('M0003', self.ho, 'Amit Patil', 'Ramesh Patil', '1958-12-03', 'M', '9876500003', 'B'),
            ('M0004', self.branch1, 'Sunita Joshi', 'Prakash Joshi', '1982-03-25', 'F', '9876500004', 'A'),
            ('M0005', self.branch1, 'Vikram Kulkarni', 'Mohan Kulkarni', '1975-07-10', 'M', '9876500005', 'A'),
            ('M0006', self.branch1, 'Rekha Bhosale', 'Sunil Bhosale', '1988-11-18', 'F', '9876500006', 'B'),
            ('M0007', self.branch2, 'Manoj Deshmukh', 'Keshav Deshmukh', '1992-01-30', 'M', '9876500007', 'A'),
            ('M0008', self.branch2, 'Anjali Pawar', 'Ganesh Pawar', '1986-06-22', 'F', '9876500008', 'A'),
            ('M0009', self.branch2, 'Sachin Jadhav', 'Baburao Jadhav', '1955-09-05', 'M', '9876500009', 'C'),
            ('M0010', self.ho, 'Deepak Wagh', 'Dattatray Wagh', '2010-04-12', 'M', '9876500010', 'A'),
            ('M0011', self.branch1, 'Kavita Shinde', 'Ramrao Shinde', '1983-02-28', 'F', '9876500011', 'A'),
            ('M0012', self.branch2, 'Nitin Gaikwad', 'Tulshiram Gaikwad', '1980-10-14', 'M', '9876500012', 'B'),
        ]

        admin = self.admin
        for member_no, branch, name, father, dob_str, gender, phone, category in members_data:
            parts = name.split()
            m, created = Member.objects.get_or_create(
                member_no=member_no,
                defaults={
                    'branch': branch,
                    'name': name,
                    'father_name': father,
                    'dob': date.fromisoformat(dob_str),
                    'gender': gender,
                    'phone': phone,
                    'address': f'{member_no} Society Lane',
                    'city': 'Pune',
                    'state': 'Maharashtra',
                    'pincode': '411001',
                    'join_date': date(2024, 1, 1),
                    'status': 'active',
                    'category': category,
                    'kyc_verified': True,
                    'kyc_date': date(2024, 1, 1),
                    'created_by': admin,
                },
            )
            self.members.append(m)

            if created:
                MemberNominee.objects.create(
                    member=m,
                    name=f'Nominee of {parts[0]}',
                    relation='Spouse',
                    dob=date(1990, 1, 1),
                    phone='9800000000',
                    share_percentage=Decimal('100.00'),
                )

        self.stdout.write(f'  Members: {len(self.members)} (across 3 branches)')

    def _seed_enhanced_member_fields(self):
        """Set category flags and extended profile fields on specific members."""
        from apps.members.models import Member

        enhancements = {
            'M0001': {
                'prefix': 'Shri',
                'is_director': True,
                'district': 'Pune',
                'tahsil': 'Haveli',
                'blood_group': 'B+',
                'education': 'Graduate',
                'religion': 'Hindu',
                'caste': 'General',
            },
            'M0003': {'prefix': 'Shri', 'is_senior_citizen': True},
            'M0004': {'prefix': 'Smt', 'is_employee': True},
            'M0006': {'prefix': 'Smt', 'is_widow': True},
            'M0007': {'prefix': 'Shri', 'is_ex_military': True},
            'M0009': {'prefix': 'Shri', 'is_senior_citizen': True, 'is_physically_disabled': True},
            'M0010': {
                'is_minor': True,
                'guardian_name': 'Dattatray Wagh',
                'guardian_address': 'MG Road, Pune',
            },
            'M0012': {'name_regional': 'नितीन गायकवाड'},
        }

        for member_no, fields in enhancements.items():
            Member.objects.filter(member_no=member_no).update(**fields)

        m0001 = Member.objects.get(member_no='M0001')
        m0010 = Member.objects.get(member_no='M0010')
        if not m0010.introducer_id:
            m0010.introducer = m0001
            m0010.save(update_fields=['introducer'])

        self.stdout.write('  Enhanced Members: 8 (director, senior, widow, military, minor, disabled, regional name)')

    def _seed_share_config(self):
        from apps.shares.models import ShareConfig

        self.share_config, _ = ShareConfig.objects.get_or_create(
            defaults={
                'face_value_per_share': Decimal('100.00'),
                'max_shares_per_member': 500,
                'min_shares_required': 10,
                'is_active': True,
            }
        )

    def _seed_shares(self):
        from apps.shares.models import ShareHolding, ShareTransaction

        cert_no = 1
        for i, member in enumerate(self.members):
            count = (i + 1) * 10
            _holding, created = ShareHolding.objects.get_or_create(
                member=member,
                defaults={
                    'branch': member.branch,
                    'share_count': count,
                    'face_value_per_share': Decimal('100.00'),
                    'total_amount': Decimal(str(count * 100)),
                    'purchase_date': date(2024, 1, 15),
                    'certificate_no': f'SC-2024-{cert_no:04d}',
                    'status': 'active',
                    'created_by': self.admin,
                },
            )
            if created:
                ShareTransaction.objects.create(
                    member=member,
                    branch=member.branch,
                    txn_type='purchase',
                    shares_count=count,
                    amount=Decimal(str(count * 100)),
                    txn_date=date(2024, 1, 15),
                    narration=f'Initial share purchase - {count} shares',
                    created_by=self.admin,
                )
            cert_no += 1

        self.stdout.write(f'  Shares: {len(self.members)} holdings (10-120 shares each)')

    def _seed_loan_products(self):
        from apps.loans.models import LoanProduct

        products = [
            (
                'Personal Loan',
                Decimal('12.00'),
                Decimal('500000.00'),
                60,
                'reducing_monthly',
                False,
                Decimal('1.00'),
                Decimal('18.00'),
                'non_mortgage',
                'none',
            ),
            (
                'Gold Loan',
                Decimal('10.00'),
                Decimal('1000000.00'),
                36,
                'reducing_monthly',
                True,
                Decimal('0.50'),
                Decimal('15.00'),
                'mortgage',
                'gold',
            ),
            (
                'Emergency Loan',
                Decimal('14.00'),
                Decimal('100000.00'),
                24,
                'flat',
                False,
                Decimal('0.00'),
                Decimal('18.00'),
                'non_mortgage',
                'none',
            ),
            (
                'Property Loan',
                Decimal('11.00'),
                Decimal('2000000.00'),
                120,
                'reducing_monthly',
                True,
                Decimal('1.00'),
                Decimal('15.00'),
                'mortgage',
                'property',
            ),
            (
                'Vehicle Loan',
                Decimal('13.00'),
                Decimal('800000.00'),
                60,
                'reducing_monthly',
                True,
                Decimal('1.50'),
                Decimal('18.00'),
                'mortgage',
                'vehicle',
            ),
        ]

        self.loan_products = []
        for name, rate, max_amt, tenure, int_type, collateral, fee, penal, category, mort_type in products:
            lp, created = LoanProduct.objects.get_or_create(
                name=name,
                defaults={
                    'interest_rate': rate,
                    'max_amount': max_amt,
                    'max_tenure_months': tenure,
                    'interest_type': int_type,
                    'loan_category': category,
                    'mortgage_type': mort_type,
                    'allow_multiple': category == 'mortgage',
                    'requires_guarantor': True,
                    'max_guarantors': 2,
                    'guarantor_must_be_shareholder': True,
                    'requires_collateral': collateral,
                    'processing_fee_percent': fee,
                    'penal_interest_rate': penal,
                    'npa_days_threshold': 90,
                    'is_active': True,
                },
            )
            if not created:
                lp.loan_category = category
                lp.mortgage_type = mort_type
                lp.allow_multiple = category == 'mortgage'
                lp.guarantor_must_be_shareholder = True
                lp.save(
                    update_fields=[
                        'loan_category',
                        'mortgage_type',
                        'allow_multiple',
                        'guarantor_must_be_shareholder',
                    ]
                )
            self.loan_products.append(lp)

        self.stdout.write(f'  Loan Products: {len(self.loan_products)} (3 non-mortgage + 2 mortgage)')

    def _seed_fd_products(self):
        from apps.deposits.models import FDProduct

        self.fd_products = []
        products = [
            (
                'Regular FD',
                Decimal('10000.00'),
                Decimal('5000000.00'),
                90,
                3650,
                [
                    {'min_days': 90, 'max_days': 180, 'rate': 6.0, 'senior_rate': 6.5},
                    {'min_days': 181, 'max_days': 365, 'rate': 7.0, 'senior_rate': 7.5},
                    {'min_days': 366, 'max_days': 730, 'rate': 7.5, 'senior_rate': 8.0},
                    {'min_days': 731, 'max_days': 3650, 'rate': 8.0, 'senior_rate': 8.5},
                ],
                'quarterly',
                Decimal('1.00'),
            ),
            (
                'Tax Saving FD',
                Decimal('10000.00'),
                Decimal('150000.00'),
                1825,
                1825,
                [{'min_days': 1825, 'max_days': 1825, 'rate': 7.5, 'senior_rate': 8.0}],
                'cumulative',
                Decimal('1.50'),
            ),
        ]

        for name, min_a, max_a, min_d, max_d, rates, compound, penalty in products:
            fp, _ = FDProduct.objects.get_or_create(
                name=name,
                defaults={
                    'min_amount': min_a,
                    'max_amount': max_a,
                    'min_tenure_days': min_d,
                    'max_tenure_days': max_d,
                    'interest_rates': rates,
                    'compounding': compound,
                    'premature_penalty_percent': penalty,
                    'is_active': True,
                },
            )
            self.fd_products.append(fp)

        self.stdout.write(f'  FD Products: {len(self.fd_products)}')

    def _seed_savings_accounts(self):
        from apps.savings.models import SavingsAccount

        self.savings_accounts = []
        for i, member in enumerate(self.members):
            acct_no = f'{member.branch.branch_code}-SA-{i + 1:05d}'
            sa, _ = SavingsAccount.objects.get_or_create(
                member=member,
                account_no=acct_no,
                defaults={
                    'branch': member.branch,
                    'account_type': 'savings',
                    'opening_date': date(2024, 1, 15),
                    'status': 'active',
                    'current_balance': Decimal('0.00'),
                    'interest_rate': Decimal('6.00'),
                    'minimum_balance': Decimal('500.00'),
                },
            )
            self.savings_accounts.append(sa)

        self.stdout.write(f'  Savings Accounts: {len(self.savings_accounts)}')

    def _seed_savings_transactions(self):
        from apps.savings.models import AccountTransaction

        deposits = [
            (0, Decimal('50000.00'), 'Initial deposit'),
            (1, Decimal('75000.00'), 'Initial deposit'),
            (2, Decimal('30000.00'), 'Initial deposit'),
            (3, Decimal('100000.00'), 'Initial deposit'),
            (4, Decimal('45000.00'), 'Initial deposit'),
            (5, Decimal('60000.00'), 'Initial deposit'),
            (6, Decimal('25000.00'), 'Initial deposit'),
            (7, Decimal('80000.00'), 'Initial deposit'),
            (8, Decimal('15000.00'), 'Initial deposit'),
            (9, Decimal('55000.00'), 'Initial deposit'),
            (10, Decimal('40000.00'), 'Initial deposit'),
            (11, Decimal('35000.00'), 'Initial deposit'),
        ]

        txn_count = 0
        for idx, amount, narration in deposits:
            sa = self.savings_accounts[idx]
            member = self.members[idx]
            _, created = AccountTransaction.objects.get_or_create(
                account=sa,
                voucher_no=f'DEP-SEED-{idx + 1:04d}',
                defaults={
                    'branch': member.branch,
                    'txn_date': date(2024, 2, 1),
                    'value_date': date(2024, 2, 1),
                    'txn_type': 'deposit',
                    'amount': amount,
                    'running_balance': amount,
                    'narration': narration,
                    'receipt_no': f'R-SEED-{idx + 1:04d}',
                    'payment_mode': 'cash',
                    'created_by': self.admin,
                },
            )
            if created:
                sa.current_balance = amount
                sa.save(update_fields=['current_balance'])
                txn_count += 1

        extra_txns = [
            (0, Decimal('10000.00'), 'deposit', 'Monthly salary deposit', date(2024, 3, 5)),
            (0, Decimal('5000.00'), 'withdrawal', 'ATM withdrawal', date(2024, 3, 10)),
            (1, Decimal('20000.00'), 'deposit', 'Business income', date(2024, 3, 8)),
            (3, Decimal('15000.00'), 'deposit', 'Bonus deposit', date(2024, 3, 12)),
            (3, Decimal('8000.00'), 'withdrawal', 'Bill payment', date(2024, 3, 15)),
            (4, Decimal('12000.00'), 'deposit', 'Rent received', date(2024, 3, 7)),
            (7, Decimal('25000.00'), 'deposit', 'Investment return', date(2024, 3, 20)),
        ]

        for idx, amount, txn_type, narration, txn_date in extra_txns:
            sa = self.savings_accounts[idx]
            member = self.members[idx]
            if txn_type == 'deposit':
                new_balance = sa.current_balance + amount
            else:
                new_balance = sa.current_balance - amount

            voucher = f'{"DEP" if txn_type == "deposit" else "WDR"}-SEED-X{idx}-{txn_date.day:02d}'
            _, created = AccountTransaction.objects.get_or_create(
                account=sa,
                voucher_no=voucher,
                defaults={
                    'branch': member.branch,
                    'txn_date': txn_date,
                    'value_date': txn_date,
                    'txn_type': txn_type,
                    'amount': amount,
                    'running_balance': new_balance,
                    'narration': narration,
                    'receipt_no': f'R-{voucher}',
                    'payment_mode': 'cash',
                    'created_by': self.admin,
                },
            )
            if created:
                sa.current_balance = new_balance
                sa.save(update_fields=['current_balance'])
                txn_count += 1

        self.stdout.write(f'  Savings Transactions: {txn_count}')

    def _seed_loans(self):
        from apps.loans.models import EMISchedule, LoanAccount, LoanGuarantor

        loans_data = [
            (0, 0, Decimal('200000.00'), 24, 'disbursed', 'LF-2024-001'),
            (3, 0, Decimal('100000.00'), 12, 'disbursed', 'LF-2024-002'),
            (4, 1, Decimal('300000.00'), 36, 'disbursed', 'LF-2024-003'),
            (7, 2, Decimal('50000.00'), 12, 'disbursed', 'LF-2024-004'),
            (1, 0, Decimal('150000.00'), 18, 'applied', 'LF-2024-005'),
            (9, 0, Decimal('75000.00'), 12, 'approved', 'LF-2024-006'),
        ]

        loan_count = 0
        for idx, prod_idx, amount, tenure, status, form_no in loans_data:
            member = self.members[idx]
            product = self.loan_products[prod_idx]
            loan_no = f'LN-{date.today().year}-{loan_count + 1:04d}'

            loan, created = LoanAccount.objects.get_or_create(
                loan_no=loan_no,
                defaults={
                    'member': member,
                    'branch': member.branch,
                    'loan_product': product,
                    'applied_date': date(2024, 2, 1),
                    'applied_amount': amount,
                    'interest_rate': product.interest_rate,
                    'tenure_months': tenure,
                    'status': 'applied',
                    'loan_form_no': form_no,
                },
            )

            if created:
                if status in ('approved', 'disbursed'):
                    loan.approved_date = date(2024, 2, 5)
                    loan.approved_amount = amount
                    loan.approved_by = self.admin
                    loan.sanction_date = date(2024, 2, 5)
                    loan.sanction_amount = amount
                    loan.status = 'approved'

                if status == 'disbursed':
                    loan.disbursed_date = date(2024, 2, 10)
                    loan.disbursed_amount = amount
                    loan.outstanding_principal = amount
                    loan.status = 'disbursed'

                    r = product.interest_rate / Decimal('1200')
                    n = tenure
                    if product.interest_type == 'flat':
                        total_interest = amount * product.interest_rate * Decimal(str(tenure)) / Decimal('1200')
                        emi = (amount + total_interest) / Decimal(str(tenure))
                    else:
                        if r > 0:
                            emi = amount * r * (1 + r) ** n / ((1 + r) ** n - 1)
                        else:
                            emi = amount / Decimal(str(n))
                    emi = emi.quantize(Decimal('0.01'))
                    loan.emi_amount = emi
                    loan.pending_installments = tenure

                    outstanding = amount
                    for i in range(1, tenure + 1):
                        if product.interest_type == 'flat':
                            interest_comp = amount * product.interest_rate / Decimal('1200')
                            principal_comp = emi - interest_comp
                        else:
                            interest_comp = (outstanding * product.interest_rate / Decimal('1200')).quantize(
                                Decimal('0.01')
                            )
                            principal_comp = emi - interest_comp

                        if i == tenure:
                            principal_comp = outstanding
                            interest_comp = emi - principal_comp
                            if interest_comp < 0:
                                interest_comp = Decimal('0.00')

                        EMISchedule.objects.create(
                            loan=loan,
                            installment_no=i,
                            due_date=date(2024, 2, 10) + timedelta(days=30 * i),
                            principal_component=principal_comp.quantize(Decimal('0.01')),
                            interest_component=interest_comp.quantize(Decimal('0.01')),
                            total_emi=emi,
                            status='pending',
                        )
                        outstanding -= principal_comp

                loan.save()

                guarantor_idx = (idx + 1) % len(self.members)
                LoanGuarantor.objects.create(
                    loan=loan,
                    guarantor_member=self.members[guarantor_idx],
                    guarantee_amount=amount,
                )

                loan_count += 1

        self.stdout.write(f'  Loans: {loan_count} (4 disbursed, 1 applied, 1 approved)')

    def _seed_fixed_deposits(self):
        from apps.deposits.models import FixedDeposit

        fds_data = [
            (0, 0, Decimal('100000.00'), 365, Decimal('7.00')),
            (1, 0, Decimal('200000.00'), 730, Decimal('7.50')),
            (3, 0, Decimal('50000.00'), 180, Decimal('6.00')),
            (7, 0, Decimal('150000.00'), 365, Decimal('7.00')),
        ]

        fd_count = 0
        for idx, prod_idx, amount, tenure, rate in fds_data:
            member = self.members[idx]
            product = self.fd_products[prod_idx]
            fd_no = f'FD-{date.today().year}-{fd_count + 1:04d}'

            start = date(2024, 3, 1)
            maturity = start + timedelta(days=tenure)

            if product.compounding == 'quarterly':
                quarters = Decimal(str(tenure)) / Decimal('365') * Decimal('4')
                maturity_amt = amount * (1 + rate / Decimal('400')) ** int(quarters)
            else:
                maturity_amt = amount * (1 + rate * Decimal(str(tenure)) / Decimal('36500'))
            maturity_amt = maturity_amt.quantize(Decimal('0.01'))

            _, created = FixedDeposit.objects.get_or_create(
                fd_no=fd_no,
                defaults={
                    'member': member,
                    'branch': member.branch,
                    'fd_product': product,
                    'deposit_amount': amount,
                    'interest_rate': rate,
                    'start_date': start,
                    'maturity_date': maturity,
                    'tenure_days': tenure,
                    'maturity_amount': maturity_amt,
                    'compounding_type': product.compounding,
                    'status': 'active',
                    'is_auto_renew': False,
                    'certificate_no': f'FDC-{fd_count + 1:04d}',
                    'created_by': self.admin,
                },
            )
            if created:
                fd_count += 1

        self.stdout.write(f'  Fixed Deposits: {fd_count}')

    def _seed_recurring_deposits(self):
        from apps.deposits.models import RDInstallment, RecurringDeposit

        rds_data = [
            (2, Decimal('2000.00'), Decimal('7.00'), 24),
            (5, Decimal('5000.00'), Decimal('7.50'), 36),
            (9, Decimal('1000.00'), Decimal('6.50'), 12),
        ]

        rd_count = 0
        for idx, monthly, rate, tenure in rds_data:
            member = self.members[idx]
            rd_no = f'RD-{date.today().year}-{rd_count + 1:04d}'
            start = date(2024, 3, 1)
            maturity = start + timedelta(days=30 * tenure)
            maturity_amt = monthly * Decimal(str(tenure)) * (1 + rate / Decimal('200'))
            maturity_amt = maturity_amt.quantize(Decimal('0.01'))

            rd, created = RecurringDeposit.objects.get_or_create(
                rd_no=rd_no,
                defaults={
                    'member': member,
                    'branch': member.branch,
                    'monthly_installment': monthly,
                    'interest_rate': rate,
                    'start_date': start,
                    'maturity_date': maturity,
                    'tenure_months': tenure,
                    'maturity_amount': maturity_amt,
                    'status': 'active',
                    'created_by': self.admin,
                },
            )

            if created:
                for i in range(1, tenure + 1):
                    due = start + timedelta(days=30 * i)
                    is_paid = i <= 3
                    RDInstallment.objects.create(
                        rd=rd,
                        installment_no=i,
                        due_date=due,
                        amount=monthly,
                        paid_amount=monthly if is_paid else Decimal('0.00'),
                        paid_date=due if is_paid else None,
                        status='paid' if is_paid else 'pending',
                    )
                rd_count += 1

        self.stdout.write(f'  Recurring Deposits: {rd_count}')

    def _seed_agents(self):
        from apps.agents.models import Agent, AgentCollection, PigmmyAccount

        cashier_ho = self.users.get('cashier_ho')
        cashier_br1 = self.users.get('cashier_br1')

        m0001 = self.members[0]
        m0004 = self.members[3]
        sa_m0001 = self.savings_accounts[0]
        sa_m0004 = self.savings_accounts[3]

        agent1, _ = Agent.objects.get_or_create(
            agent_code='AGT-001',
            defaults={
                'member': m0001,
                'branch': self.ho,
                'savings_account': sa_m0001,
                'security_deposit_amount': Decimal('5000.00'),
                'commission_rate': Decimal('2.00'),
                'joining_date': date(2024, 2, 1),
                'phone': '9876500001',
                'area': 'Shivajinagar, Deccan Gymkhana, FC Road',
                'status': 'active',
                'created_by': cashier_ho or self.admin,
            },
        )

        agent2, _ = Agent.objects.get_or_create(
            agent_code='AGT-002',
            defaults={
                'member': m0004,
                'branch': self.branch1,
                'savings_account': sa_m0004,
                'security_deposit_amount': Decimal('5000.00'),
                'commission_rate': Decimal('2.50'),
                'joining_date': date(2024, 3, 1),
                'phone': '9876500004',
                'area': 'Kothrud, Karve Nagar, Warje',
                'status': 'active',
                'created_by': cashier_br1 or self.admin,
            },
        )

        pigmmy_data = [
            (self.members[1], self.savings_accounts[1], agent1, self.ho, Decimal('100.00')),
            (self.members[2], self.savings_accounts[2], agent1, self.ho, Decimal('50.00')),
            (self.members[4], self.savings_accounts[4], agent2, self.branch1, Decimal('200.00')),
            (self.members[5], self.savings_accounts[5], agent2, self.branch1, Decimal('100.00')),
        ]

        pigmmy_count = 0
        for i, (member, sa, agent, branch, daily_amt) in enumerate(pigmmy_data):
            period = 12
            start = date(2024, 4, 1)
            maturity = start + timedelta(days=365)
            total_installments = 365 if True else period * 30

            _pa, created = PigmmyAccount.objects.get_or_create(
                account_no=f'PG-{branch.branch_code}-{i + 1:04d}',
                defaults={
                    'member': member,
                    'branch': branch,
                    'agent': agent,
                    'linked_savings_account': sa,
                    'deposit_type': 'daily',
                    'installment_amount': daily_amt,
                    'deposit_period_months': period,
                    'interest_rate': Decimal('5.00'),
                    'opening_date': start,
                    'maturity_date': maturity,
                    'total_installments': total_installments,
                    'status': 'active',
                    'created_by': self.admin,
                },
            )
            if created:
                pigmmy_count += 1

        today = date.today()
        collection_dates = [today - timedelta(days=i) for i in range(6, 0, -1)]

        for agent, branch in [(agent1, self.ho), (agent2, self.branch1)]:
            for cdate in collection_dates[:3]:
                AgentCollection.objects.get_or_create(
                    agent=agent,
                    collection_date=cdate,
                    defaults={
                        'branch': branch,
                        'total_clients_visited': 2,
                        'total_clients_collected': 2,
                        'expected_amount': Decimal('150.00') if agent == agent1 else Decimal('300.00'),
                        'collected_amount': Decimal('150.00') if agent == agent1 else Decimal('300.00'),
                        'deposited_amount': Decimal('150.00') if agent == agent1 else Decimal('300.00'),
                        'commission_amount': Decimal('3.00') if agent == agent1 else Decimal('7.50'),
                        'status': 'reconciled',
                    },
                )

        self.stdout.write(f'  Agents: 2 | Pigmmy Accounts: {pigmmy_count} | Collections: 6')

    def _seed_working_day(self):
        from apps.dayend.models import WorkingDay

        today = date.today()
        for branch in [self.ho, self.branch1, self.branch2]:
            WorkingDay.objects.get_or_create(
                branch=branch,
                defaults={
                    'current_date': today,
                    'is_day_open': True,
                    'opened_by': self.admin,
                    'opened_at': timezone.now(),
                },
            )

        self.stdout.write(f'  Working Days: 3 (all branches open for {today})')

    def _print_summary(self):
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 65))
        self.stdout.write(self.style.SUCCESS('  INFOSOCIETY — TEST DATA SUMMARY'))
        self.stdout.write(self.style.SUCCESS('=' * 65))
        self.stdout.write('')
        self.stdout.write('  Login Credentials (password for all: test123)')
        self.stdout.write('  ' + '-' * 50)
        self.stdout.write('  admin        / admin123   -> Super Admin (HO)')
        self.stdout.write('  manager_ho   / test123    -> Branch Manager (HO)')
        self.stdout.write('  cashier_ho   / test123    -> Cashier (HO)')
        self.stdout.write('  accountant   / test123    -> Accountant (HO)')
        self.stdout.write('  manager_br1  / test123    -> Branch Manager (Kothrud)')
        self.stdout.write('  cashier_br1  / test123    -> Cashier (Kothrud)')
        self.stdout.write('  manager_br2  / test123    -> Branch Manager (Hadapsar)')
        self.stdout.write('  cashier_br2  / test123    -> Cashier (Hadapsar)')
        self.stdout.write('  auditor      / test123    -> Auditor (Read-only)')
        self.stdout.write('')
        self.stdout.write('  Test Data Created')
        self.stdout.write('  ' + '-' * 50)
        self.stdout.write('  Branches           : 3 (HO + Kothrud + Hadapsar)')
        self.stdout.write('  Members            : 12 (4 per branch, with category flags)')
        self.stdout.write('    - M0001: Director, Shri prefix')
        self.stdout.write('    - M0003: Senior Citizen (age 60+)')
        self.stdout.write('    - M0004: Employee, Smt prefix')
        self.stdout.write('    - M0006: Widow')
        self.stdout.write('    - M0007: Ex-Military')
        self.stdout.write('    - M0009: Senior + Physically Disabled (+0.50% FD bonus)')
        self.stdout.write('    - M0010: Minor with guardian')
        self.stdout.write('    - M0012: Regional name in Marathi')
        self.stdout.write('  Share Holdings     : 12 (10-120 shares each)')
        self.stdout.write('  Savings Accounts   : 12 (with initial deposits)')
        self.stdout.write('  Savings Txns       : ~19 (deposits + withdrawals)')
        self.stdout.write('  Loan Products      : 5 (Personal/Gold/Emergency/Property/Vehicle)')
        self.stdout.write('    - Non-mortgage: Personal, Emergency')
        self.stdout.write('    - Mortgage: Gold, Property, Vehicle')
        self.stdout.write('  Loans              : 6 (4 disbursed + 1 applied + 1 approved)')
        self.stdout.write('  FD Products        : 2 (Regular + Tax Saving)')
        self.stdout.write('  Fixed Deposits     : 4 (active)')
        self.stdout.write('  Recurring Deposits : 3 (with installment schedules)')
        self.stdout.write('  Agents             : 2 (HO + Kothrud)')
        self.stdout.write('  Pigmmy Accounts    : 4 (daily collection)')
        self.stdout.write('  Agent Collections  : 6 (3 per agent, reconciled)')
        self.stdout.write('  Working Days       : 3 (all branches, today, open)')
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 65))
