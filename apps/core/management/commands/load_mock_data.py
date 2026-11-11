"""
Create comprehensive mock data for testing all InfoSociety flows.
Usage: python manage.py load_mock_data --tenant demo
       python manage.py load_mock_data --tenant demo --flush
"""

from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django_tenants.utils import get_tenant_model


class Command(BaseCommand):
    help = 'Load comprehensive mock data for testing every module'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', type=str, default='demo', help='Tenant schema name')
        parser.add_argument('--flush', action='store_true', help='Delete all existing data first')

    def handle(self, *args, **options):
        schema = options['tenant']
        tenant_model = get_tenant_model()
        try:
            tenant = tenant_model.objects.get(schema_name=schema)
        except tenant_model.DoesNotExist:
            self.stderr.write(
                self.style.ERROR(
                    f'Tenant "{schema}" not found. Available: '
                    f'{", ".join(tenant_model.objects.values_list("schema_name", flat=True))}'
                )
            )
            return

        connection.set_tenant(tenant)
        self.stdout.write(f'Schema: {schema}')

        if options['flush']:
            self._flush_all()

        self._update_subscription_plans()

        with transaction.atomic():
            ho, city = self._create_branches()
            admin, cashier, manager, _accountant = self._create_staff(ho)
            members = self._create_members(ho, admin)
            self._create_financial_year()
            self._setup_coa(ho, city)
            self._create_share_config_and_holdings(members, ho, admin)
            savings = self._create_savings_accounts(members, ho, admin)
            self._create_savings_transactions(savings, admin)
            fd_product, rd_product, loan_products = self._create_products()
            self._create_fds(members, ho, fd_product, admin)
            self._create_rds(members, ho, rd_product, admin)
            loans = self._create_loans(members, ho, loan_products, admin, manager, cashier)
            self._create_loan_guarantors(members, loans)
            self._create_pigmmy(members, ho, admin)
            self._create_interest_master()
            self._create_working_days(ho)
            self._create_member_nominees(members)
            self._create_agent_collections(admin)

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('All mock data loaded!'))
        self.stdout.write('')
        self.stdout.write('  Login Credentials:')
        self.stdout.write('  ──────────────────')
        self.stdout.write('  Admin:      admin / admin123')
        self.stdout.write('  Manager:    manager1 / staff123')
        self.stdout.write('  Cashier:    cashier1 / staff123')
        self.stdout.write('  Accountant: accountant1 / staff123')
        self.stdout.write('')
        self.stdout.write('  Data Summary:')
        self.stdout.write('  ─────────────')
        self.stdout.write('  2 branches, 4 staff, 10 members')
        self.stdout.write('  10 share holdings, 10 savings accounts')
        self.stdout.write('  Savings deposits/withdrawals per account')
        self.stdout.write('  1 FD product (4 slabs) + 1 RD product')
        self.stdout.write('  3 FDs (active, matured, auto-renew)')
        self.stdout.write('  2 RDs with installments')
        self.stdout.write('  3 loan products (personal, gold, emergency)')
        self.stdout.write('  4 loans (applied, approved, disbursed, NPA)')
        self.stdout.write('  Guarantors on disbursed loans')
        self.stdout.write('  1 pigmmy agent + 3 accounts')
        self.stdout.write('  Financial year 2025-26')
        self.stdout.write('  Interest master slabs for all account types')
        self.stdout.write('  Working day open for today')
        self.stdout.write('  Member nominees')
        self.stdout.write('  Agent collections')

    def _update_subscription_plans(self):
        from apps.tenants.models import SubscriptionPlan

        plans_data = [
            {
                'name': 'Basic',
                'defaults': {
                    'max_members': 100,
                    'max_branches': 1,
                    'max_users': 3,
                    'price_monthly': Decimal('1000.00'),
                    'features': {
                        'savings': 'Savings Accounts',
                        'loans': 'Loan Management',
                        'reports': 'Reports & Analytics',
                    },
                    'is_active': True,
                },
            },
            {
                'name': 'Professional',
                'defaults': {
                    'max_members': 1000,
                    'max_branches': 5,
                    'max_users': 10,
                    'price_monthly': Decimal('5000.00'),
                    'features': {
                        'savings': 'Savings Accounts',
                        'loans': 'Loan Management',
                        'fd': 'Fixed Deposits',
                        'rd': 'Recurring Deposits',
                        'sms': 'SMS Notifications',
                        'reports': 'Reports & Analytics',
                    },
                    'is_active': True,
                },
            },
            {
                'name': 'Enterprise',
                'defaults': {
                    'max_members': 99999,
                    'max_branches': 20,
                    'max_users': 50,
                    'price_monthly': Decimal('15000.00'),
                    'features': {
                        'savings': 'Savings Accounts',
                        'loans': 'Loan Management',
                        'fd': 'Fixed Deposits',
                        'rd': 'Recurring Deposits',
                        'sms': 'SMS Notifications',
                        'reports': 'Reports & Analytics',
                    },
                    'is_active': True,
                },
            },
        ]
        for p in plans_data:
            SubscriptionPlan.objects.update_or_create(name=p['name'], defaults=p['defaults'])
        self.stdout.write('  3 subscription plans updated')

    def _flush_all(self):
        from apps.accounting.models import CashbookMaster, ChartOfAccounts, InterestMaster, JournalEntry, JournalLine
        from apps.accounts.models import CustomUser
        from apps.agents.models import Agent, AgentCollection, AgentCommission, PigmmyAccount, PigmmyTransaction
        from apps.branches.models import Branch
        from apps.dayend.models import DayEndLog, FinancialYear, MonthEndLog, WorkingDay, YearEndLog
        from apps.deposits.models import FDProduct, FixedDeposit, RDInstallment, RDProduct, RecurringDeposit
        from apps.loans.models import (
            EMISchedule,
            LoanAccount,
            LoanCollateral,
            LoanGuarantor,
            LoanProduct,
            LoanRepayment,
            StandingInstruction,
        )
        from apps.members.models import Member, MemberDocument, MemberNominee
        from apps.savings.models import AccountTransaction, SavingsAccount
        from apps.shares.models import ShareConfig, ShareHolding, ShareTransaction

        self.stdout.write('  Flushing all data...')
        for model in [
            AgentCommission,
            AgentCollection,
            PigmmyTransaction,
            PigmmyAccount,
            Agent,
            RDInstallment,
            RecurringDeposit,
            FixedDeposit,
            RDProduct,
            FDProduct,
            StandingInstruction,
            LoanRepayment,
            EMISchedule,
            LoanCollateral,
            LoanGuarantor,
            LoanAccount,
            LoanProduct,
            AccountTransaction,
            SavingsAccount,
            ShareTransaction,
            ShareHolding,
            ShareConfig,
            JournalLine,
            JournalEntry,
            CashbookMaster,
            InterestMaster,
            YearEndLog,
            MonthEndLog,
            DayEndLog,
            WorkingDay,
            FinancialYear,
            MemberDocument,
            MemberNominee,
            Member,
            ChartOfAccounts,
            CustomUser,
            Branch,
        ]:
            model.objects.all().delete()
        self.stdout.write(self.style.SUCCESS('  Flushed.'))

    def _create_branches(self):
        from apps.branches.models import Branch

        ho = Branch.objects.create(
            branch_code='BR01',
            branch_name='Head Office',
            address='123 MG Road, Camp Area',
            city='Pune',
            state='Maharashtra',
            pincode='411001',
            phone='020-25551234',
            email='ho@infosociety.com',
            is_head_office=True,
            opening_date=date(2020, 1, 1),
            status='active',
        )
        city = Branch.objects.create(
            branch_code='BR02',
            branch_name='City Branch',
            address='45 FC Road, Deccan',
            city='Pune',
            state='Maharashtra',
            pincode='411004',
            phone='020-25554567',
            email='city@infosociety.com',
            is_head_office=False,
            opening_date=date(2021, 4, 1),
            status='active',
        )
        self.stdout.write('  2 branches')
        return ho, city

    def _create_staff(self, branch):
        from apps.accounts.models import CustomUser

        def make_user(username, first, last, role, all_branches=False, **kw):
            u = CustomUser.objects.create(
                username=username,
                first_name=first,
                last_name=last,
                email=f'{username}@infosociety.com',
                role=role,
                branch=branch,
                can_access_all_branches=all_branches,
                **kw,
            )
            u.set_password('admin123' if username == 'admin' else 'staff123')
            u.save()
            return u

        admin = make_user('admin', 'System', 'Admin', 'admin', all_branches=True, is_staff=True, is_superuser=True)
        manager = make_user('manager1', 'Ramesh', 'Manager', 'branch_manager')
        cashier = make_user('cashier1', 'Priya', 'Cashier', 'cashier')
        accountant = make_user('accountant1', 'Vikram', 'Accountant', 'accountant')
        self.stdout.write('  4 staff users')
        return admin, cashier, manager, accountant

    def _create_members(self, branch, created_by):
        from apps.members.models import Member, MemberNominee

        data = [
            (
                'M001',
                'Rajesh Kumar',
                'male',
                '9876543210',
                date(1985, 5, 15),
                'Business',
                Decimal('50000'),
                True,
                False,
                False,
            ),
            (
                'M002',
                'Sunil Patil',
                'male',
                '9876543211',
                date(1980, 8, 20),
                'Teacher',
                Decimal('35000'),
                True,
                False,
                False,
            ),
            (
                'M003',
                'Amit Kulkarni',
                'male',
                '9876543212',
                date(1958, 3, 10),
                'Retired',
                Decimal('20000'),
                False,
                True,
                False,
            ),
            (
                'M004',
                'Sneha Deshmukh',
                'female',
                '9876543213',
                date(1995, 12, 1),
                'IT Professional',
                Decimal('75000'),
                False,
                False,
                False,
            ),
            (
                'M005',
                'Ganesh Jadhav',
                'male',
                '9876543214',
                date(1975, 7, 25),
                'Shopkeeper',
                Decimal('30000'),
                False,
                False,
                True,
            ),
            (
                'M006',
                'Priya Sharma',
                'female',
                '9876543215',
                date(1992, 1, 14),
                'Nurse',
                Decimal('28000'),
                False,
                False,
                False,
            ),
            (
                'M007',
                'Vikram Rane',
                'male',
                '9876543216',
                date(1988, 6, 5),
                'Contractor',
                Decimal('60000'),
                True,
                False,
                False,
            ),
            (
                'M008',
                'Lata Bhosle',
                'female',
                '9876543217',
                date(1955, 11, 8),
                'Retired',
                Decimal('15000'),
                False,
                True,
                False,
            ),
            (
                'M009',
                'Deepak More',
                'male',
                '9876543218',
                date(1990, 4, 22),
                'Driver',
                Decimal('18000'),
                False,
                False,
                True,
            ),
            (
                'M010',
                'Anita Pawar',
                'female',
                '9876543219',
                date(1987, 9, 30),
                'Tailor',
                Decimal('22000'),
                False,
                False,
                False,
            ),
        ]

        members = []
        for mno, name, gender, phone, dob, occ, income, is_dir, is_sr, is_emp in data:
            m = Member.objects.create(
                member_no=mno,
                name=name,
                gender=gender,
                phone=phone,
                dob=dob,
                occupation=occ,
                monthly_income=income,
                father_name=f'{name} Father',
                address=f'{mno} Test Street',
                city='Pune',
                state='Maharashtra',
                pincode='411001',
                branch=branch,
                join_date=date(2024, 4, 1),
                status='active',
                category='A',
                created_by=created_by,
                is_director=is_dir,
                is_senior_citizen=is_sr,
                is_employee=is_emp,
            )
            MemberNominee.objects.create(
                member=m,
                name=f'{name} Nominee',
                relation='Spouse',
                share_percentage=100,
                is_primary=True,
            )
            members.append(m)

        self.stdout.write('  10 members with nominees')
        return members

    def _create_financial_year(self):
        from apps.dayend.models import FinancialYear

        FinancialYear.objects.create(
            fy_code='2025-26',
            start_date=date(2025, 4, 1),
            end_date=date(2026, 3, 31),
            is_current=True,
        )
        self.stdout.write('  Financial year 2025-26')

    def _setup_coa(self, ho, city):
        from apps.accounting.initial_coa import setup_chart_of_accounts

        setup_chart_of_accounts(branches=[ho, city])
        self.stdout.write('  Chart of Accounts initialized')

    def _create_share_config_and_holdings(self, members, branch, user):
        from apps.shares.models import ShareConfig
        from apps.shares.services import purchase_shares

        ShareConfig.objects.create(
            face_value_per_share=Decimal('100'),
            max_shares_per_member=500,
            min_shares_required=1,
            is_active=True,
        )
        counts = [50, 30, 20, 10, 25, 15, 40, 10, 20, 10]
        for m, c in zip(members, counts):
            try:
                purchase_shares(member=m, branch=branch, count=c, user=user)
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  Share skip {m.name}: {e}'))
        self.stdout.write('  10 share holdings')

    def _create_savings_accounts(self, members, branch, user):
        from apps.core.account_utils import generate_account_number
        from apps.savings.models import SavingsAccount

        accounts = []
        balances = [
            Decimal('25000'),
            Decimal('15000'),
            Decimal('50000'),
            Decimal('8000'),
            Decimal('12000'),
            Decimal('6000'),
            Decimal('35000'),
            Decimal('75000'),
            Decimal('3000'),
            Decimal('18000'),
        ]
        rates = [
            Decimal('4.0'),
            Decimal('4.0'),
            Decimal('4.5'),
            Decimal('4.0'),
            Decimal('4.0'),
            Decimal('4.0'),
            Decimal('4.0'),
            Decimal('4.5'),
            Decimal('4.0'),
            Decimal('4.0'),
        ]
        for i, m in enumerate(members):
            sa = SavingsAccount.objects.create(
                member=m,
                branch=branch,
                account_no=generate_account_number(branch, '001'),
                account_type='savings',
                interest_rate=rates[i],
                minimum_balance=Decimal('500'),
                current_balance=balances[i],
                opening_date=date(2024, 4, 1),
                status='active',
                created_by=user,
            )
            accounts.append(sa)
        self.stdout.write('  10 savings accounts')

        type_codes = {'current': '002', 'security': '003'}
        for i in range(min(3, len(members))):
            ca = SavingsAccount.objects.create(
                member=members[i],
                branch=branch,
                account_no=generate_account_number(branch, type_codes['current']),
                account_type='current',
                interest_rate=Decimal('0.0'),
                minimum_balance=Decimal('1000'),
                current_balance=[Decimal('45000'), Decimal('32000'), Decimal('18000')][i],
                opening_date=date(2024, 4, 1),
                status='active',
                created_by=user,
            )
            accounts.append(ca)
        self.stdout.write('  3 current accounts')

        for i in range(min(2, len(members))):
            sd = SavingsAccount.objects.create(
                member=members[i],
                branch=branch,
                account_no=generate_account_number(branch, type_codes['security']),
                account_type='security',
                interest_rate=Decimal('0.0'),
                minimum_balance=Decimal('0'),
                current_balance=[Decimal('10000'), Decimal('5000')][i],
                opening_date=date(2024, 4, 1),
                status='active',
                created_by=user,
            )
            accounts.append(sd)
        self.stdout.write('  2 security deposit accounts')

        return accounts

    def _create_savings_transactions(self, accounts, user):
        from apps.savings.models import AccountTransaction

        today = date.today()
        for sa in accounts:
            running = Decimal('0')
            deposits = [
                (today - timedelta(days=180), sa.current_balance * Decimal('0.4')),
                (today - timedelta(days=120), sa.current_balance * Decimal('0.3')),
                (today - timedelta(days=60), sa.current_balance * Decimal('0.2')),
                (today - timedelta(days=30), sa.current_balance * Decimal('0.15')),
            ]
            for txn_date, amount in deposits:
                amount = amount.quantize(Decimal('0.01'))
                running += amount
                AccountTransaction.objects.create(
                    account=sa,
                    branch=sa.branch,
                    txn_date=txn_date,
                    value_date=txn_date,
                    txn_type='deposit',
                    amount=amount,
                    running_balance=running,
                    payment_mode='cash',
                    narration='Cash deposit',
                    created_by=user,
                )
            withdrawal_amt = (sa.current_balance * Decimal('0.05')).quantize(Decimal('0.01'))
            if withdrawal_amt > 0:
                running -= withdrawal_amt
                AccountTransaction.objects.create(
                    account=sa,
                    branch=sa.branch,
                    txn_date=today - timedelta(days=15),
                    value_date=today - timedelta(days=15),
                    txn_type='withdrawal',
                    amount=withdrawal_amt,
                    running_balance=running,
                    payment_mode='cash',
                    narration='Cash withdrawal',
                    created_by=user,
                )
        self.stdout.write('  Savings transactions created')

    def _create_products(self):
        from apps.deposits.models import FDProduct, RDProduct
        from apps.loans.models import LoanProduct

        fd_product = FDProduct.objects.create(
            name='Regular FD',
            min_amount=Decimal('5000'),
            max_amount=Decimal('1000000'),
            min_tenure_days=30,
            max_tenure_days=1825,
            interest_rates=[
                {'min_days': 30, 'max_days': 180, 'rate': 6.5, 'senior_rate': 7.0},
                {'min_days': 181, 'max_days': 365, 'rate': 7.0, 'senior_rate': 7.5},
                {'min_days': 366, 'max_days': 730, 'rate': 7.5, 'senior_rate': 8.0},
                {'min_days': 731, 'max_days': 1825, 'rate': 7.75, 'senior_rate': 8.25},
            ],
            compounding='quarterly',
            premature_penalty_percent=Decimal('1.0'),
            is_active=True,
        )

        rd_product = RDProduct.objects.create(
            name='Regular RD',
            min_installment=Decimal('500'),
            max_installment=Decimal('50000'),
            min_tenure_months=6,
            max_tenure_months=60,
            is_active=True,
        )

        personal = LoanProduct.objects.create(
            name='Personal Loan',
            interest_rate=Decimal('12.0'),
            max_amount=Decimal('500000'),
            max_tenure_months=60,
            interest_type='reducing_monthly',
            loan_category='non_mortgage',
            mortgage_type='none',
            requires_guarantor=True,
            min_guarantors=1,
            max_guarantors=2,
            guarantor_must_be_shareholder=True,
            processing_fee_percent=Decimal('1.0'),
            penal_interest_rate=Decimal('2.0'),
            npa_days_threshold=90,
            is_active=True,
        )
        gold = LoanProduct.objects.create(
            name='Gold Loan',
            interest_rate=Decimal('10.0'),
            max_amount=Decimal('300000'),
            max_tenure_months=36,
            interest_type='reducing_monthly',
            loan_category='mortgage',
            mortgage_type='gold',
            requires_guarantor=False,
            requires_collateral=True,
            processing_fee_percent=Decimal('0.5'),
            penal_interest_rate=Decimal('2.0'),
            npa_days_threshold=90,
            is_active=True,
        )
        emergency = LoanProduct.objects.create(
            name='Emergency Loan',
            interest_rate=Decimal('14.0'),
            max_amount=Decimal('50000'),
            max_tenure_months=12,
            interest_type='flat',
            loan_category='non_mortgage',
            mortgage_type='none',
            requires_guarantor=False,
            processing_fee_percent=Decimal('0.0'),
            penal_interest_rate=Decimal('3.0'),
            npa_days_threshold=60,
            is_active=True,
        )
        self.stdout.write('  FD, RD, 3 Loan products')
        return fd_product, rd_product, [personal, gold, emergency]

    def _create_fds(self, members, branch, product, user):
        from apps.deposits.models import FixedDeposit

        fds = [
            (members[0], Decimal('100000'), 365, date(2025, 6, 1), 'active', False),
            (members[2], Decimal('50000'), 180, date(2025, 1, 1), 'matured', False),
            (members[7], Decimal('200000'), 730, date(2025, 4, 1), 'active', True),
        ]

        for member, amount, tenure, start, status, auto_renew in fds:
            rate = product.get_rate_for_tenure(tenure, member.is_senior_citizen)
            if rate is None:
                rate = Decimal('7.0')
            rate = Decimal(str(rate))
            maturity_date = start + timedelta(days=tenure)
            from apps.deposits.services import calculate_fd_maturity

            maturity_amount = calculate_fd_maturity(amount, rate, tenure, product.compounding)

            FixedDeposit.objects.create(
                member=member,
                branch=branch,
                fd_product=product,
                fd_no=f'FD-{member.member_no}',
                deposit_amount=amount,
                interest_rate=rate,
                start_date=start,
                maturity_date=maturity_date,
                tenure_days=tenure,
                maturity_amount=maturity_amount,
                is_auto_renew=auto_renew,
                compounding_type=product.compounding,
                certificate_no=f'FDC-{member.member_no}',
                status=status,
                created_by=user,
            )

        self.stdout.write('  3 Fixed Deposits (active, matured, auto-renew)')

    def _create_rds(self, members, branch, rd_product, user):
        from apps.deposits.models import RDInstallment, RecurringDeposit

        today = date.today()
        rds_data = [
            (members[3], Decimal('2000'), 24, Decimal('6.5')),
            (members[5], Decimal('1000'), 12, Decimal('6.0')),
        ]

        for member, installment, tenure, rate in rds_data:
            start = date(2025, 7, 1)
            maturity_date = date(
                start.year + (start.month + tenure - 1) // 12,
                (start.month + tenure - 1) % 12 + 1,
                min(start.day, 28),
            )
            rd = RecurringDeposit.objects.create(
                member=member,
                rd_product=rd_product,
                branch=branch,
                rd_no=f'RD-{member.member_no}',
                monthly_installment=installment,
                interest_rate=rate,
                start_date=start,
                maturity_date=maturity_date,
                tenure_months=tenure,
                maturity_amount=installment * tenure * Decimal('1.05'),
                status='active',
                created_by=user,
            )
            months_elapsed = min((today.year - start.year) * 12 + today.month - start.month, tenure)
            for i in range(1, tenure + 1):
                m = (start.month + i - 1) % 12 + 1
                y = start.year + (start.month + i - 1) // 12
                due = date(y, m, min(start.day, 28))
                status = 'paid' if i <= months_elapsed else 'pending'
                RDInstallment.objects.create(
                    rd=rd,
                    installment_no=i,
                    due_date=due,
                    amount=installment,
                    status=status,
                    paid_amount=installment if status == 'paid' else Decimal('0'),
                    paid_date=due if status == 'paid' else None,
                )

        self.stdout.write('  2 Recurring Deposits with installments')

    def _create_loans(self, members, branch, products, admin, manager, cashier):
        from apps.core.account_utils import generate_account_number
        from apps.loans.models import EMISchedule, LoanAccount, LoanCollateral, LoanGuarantor

        personal, gold, emergency = products
        today = date.today()

        # 1. Applied loan (personal, needs guarantor)
        loan1 = LoanAccount.objects.create(
            member=members[3],
            branch=branch,
            loan_product=personal,
            loan_no=generate_account_number(branch, '010'),
            applied_date=today,
            applied_amount=Decimal('200000'),
            interest_rate=personal.interest_rate,
            penal_interest_rate=personal.penal_interest_rate,
            tenure_months=36,
            status='applied',
            created_by=cashier,
        )

        # 2. Approved gold loan (no guarantor needed, has collateral)
        loan2 = LoanAccount.objects.create(
            member=members[4],
            branch=branch,
            loan_product=gold,
            loan_no=generate_account_number(branch, '010'),
            applied_date=today - timedelta(days=10),
            applied_amount=Decimal('150000'),
            interest_rate=gold.interest_rate,
            penal_interest_rate=gold.penal_interest_rate,
            tenure_months=24,
            status='approved',
            approved_date=today - timedelta(days=5),
            approved_amount=Decimal('150000'),
            approved_by=manager,
            created_by=cashier,
        )
        LoanCollateral.objects.create(
            loan=loan2,
            collateral_type='Gold Ornaments',
            description='22K gold chain 50g',
            estimated_value=Decimal('250000'),
        )

        # 3. Disbursed personal loan (with guarantors & EMI schedule)
        loan3 = LoanAccount.objects.create(
            member=members[1],
            branch=branch,
            loan_product=personal,
            loan_no=generate_account_number(branch, '010'),
            applied_date=today - timedelta(days=60),
            applied_amount=Decimal('100000'),
            interest_rate=personal.interest_rate,
            penal_interest_rate=personal.penal_interest_rate,
            tenure_months=12,
            status='applied',
            created_by=cashier,
        )
        LoanGuarantor.objects.create(
            loan=loan3,
            guarantor_member=members[0],
            guarantee_amount=Decimal('50000'),
        )
        LoanGuarantor.objects.create(
            loan=loan3,
            guarantor_member=members[6],
            guarantee_amount=Decimal('50000'),
        )
        from apps.loans.services import approve_loan, disburse_loan

        approve_loan(loan3, Decimal('100000'), manager)
        disburse_loan(loan3, branch, cashier)

        # 4. NPA emergency loan (overdue)
        loan4 = LoanAccount.objects.create(
            member=members[8],
            branch=branch,
            loan_product=emergency,
            loan_no=generate_account_number(branch, '010'),
            applied_date=today - timedelta(days=200),
            applied_amount=Decimal('30000'),
            interest_rate=emergency.interest_rate,
            penal_interest_rate=emergency.penal_interest_rate,
            tenure_months=6,
            status='applied',
            created_by=cashier,
        )
        approve_loan(loan4, Decimal('30000'), manager)
        disburse_loan(loan4, branch, cashier)
        loan4.refresh_from_db()
        loan4.status = 'npa'
        loan4.overdue_days = 95
        loan4.overdue_amount = Decimal('8000')
        loan4.save(update_fields=['status', 'overdue_days', 'overdue_amount'])
        EMISchedule.objects.filter(loan=loan4, status='pending').update(status='overdue')

        self.stdout.write('  4 loans (applied, approved, disbursed, NPA)')
        return [loan1, loan2, loan3, loan4]

    def _create_pigmmy(self, members, branch, user):
        from apps.agents.models import Agent, PigmmyAccount, PigmmyTransaction
        from apps.core.account_utils import generate_account_number
        from apps.savings.models import SavingsAccount

        agent_member = members[4]
        savings = SavingsAccount.objects.filter(member=agent_member).first()
        if not savings:
            self.stdout.write(self.style.WARNING('  Pigmmy skipped: no savings'))
            return

        agent = Agent.objects.create(
            member=agent_member,
            agent_code='AGT001',
            branch=branch,
            savings_account=savings,
            phone=agent_member.phone,
            area='Hadapsar, Market Yard',
            commission_rate=Decimal('2.0'),
            joining_date=date(2025, 1, 1),
            status='active',
            created_by=user,
        )

        today = date.today()
        for m in members[:3]:
            acct = PigmmyAccount.objects.create(
                member=m,
                branch=branch,
                agent=agent,
                account_no=generate_account_number(branch, '020'),
                installment_amount=Decimal('100'),
                deposit_period_months=12,
                interest_rate=Decimal('5.0'),
                opening_date=today - timedelta(days=60),
                maturity_date=today + timedelta(days=305),
                maturity_amount=Decimal('36500'),
                total_installments=365,
                paid_installments=60,
                current_balance=Decimal('6000'),
                total_deposited=Decimal('6000'),
                status='active',
                created_by=user,
            )
            for day in range(1, 11):
                txn_date = today - timedelta(days=day)
                running = acct.current_balance - Decimal('100') * (10 - day)
                PigmmyTransaction.objects.create(
                    account=acct,
                    collected_by=agent,
                    branch=branch,
                    txn_date=txn_date,
                    amount=Decimal('100'),
                    running_balance=running,
                    installment_no=50 + day,
                    narration='Daily collection',
                    created_by=user,
                )

        self.stdout.write('  1 agent + 3 pigmmy accounts + transactions')

    def _create_interest_master(self):
        from apps.accounting.models import ChartOfAccounts, InterestMaster

        slabs = 0
        for related, configs in [
            (
                'saving',
                [
                    (0, 50000, 'days', Decimal('4.00'), Decimal('0.25')),
                    (50001, 100000, 'days', Decimal('4.50'), Decimal('0.25')),
                    (100001, 9999999, 'days', Decimal('5.00'), Decimal('0.50')),
                ],
            ),
            (
                'fixed',
                [
                    (30, 180, 'days', Decimal('6.50'), Decimal('0.50')),
                    (181, 365, 'days', Decimal('7.00'), Decimal('0.50')),
                    (366, 730, 'days', Decimal('7.50'), Decimal('0.50')),
                    (731, 1825, 'days', Decimal('7.75'), Decimal('0.50')),
                ],
            ),
            (
                'recurring',
                [
                    (6, 12, 'months', Decimal('6.00'), Decimal('0.50')),
                    (13, 24, 'months', Decimal('6.50'), Decimal('0.50')),
                    (25, 60, 'months', Decimal('7.00'), Decimal('0.50')),
                ],
            ),
            (
                'loan',
                [
                    (1, 12, 'months', Decimal('12.00'), Decimal('0')),
                    (13, 36, 'months', Decimal('13.00'), Decimal('0')),
                    (37, 60, 'months', Decimal('14.00'), Decimal('0')),
                ],
            ),
            (
                'client',
                [
                    (1, 6, 'months', Decimal('5.00'), Decimal('0.25')),
                    (7, 12, 'months', Decimal('5.50'), Decimal('0.25')),
                    (13, 24, 'months', Decimal('6.00'), Decimal('0.50')),
                ],
            ),
        ]:
            head = ChartOfAccounts.objects.filter(
                related_table_name=related,
                is_active=True,
            ).first()
            if not head:
                continue
            for min_p, max_p, unit, rate, senior_extra in configs:
                kw = {
                    'account_head': head,
                    'min_period': min_p,
                    'max_period': max_p,
                    'period_unit': unit,
                    'interest_rate': rate,
                }
                if related != 'loan':
                    kw['senior_citizen_extra'] = senior_extra
                else:
                    kw['penal_rate'] = Decimal('2.00')
                InterestMaster.objects.create(**kw)
                slabs += 1

        self.stdout.write(f'  {slabs} interest master slabs')

    def _create_working_days(self, branch):
        from datetime import date as _date

        from apps.dayend.models import WorkingDay

        today = _date.today()
        _wd, created = WorkingDay.objects.get_or_create(
            branch=branch,
            defaults={'current_date': today, 'is_day_open': True},
        )
        if created:
            self.stdout.write(f'  Working day created for {today}')
        else:
            self.stdout.write(f'  Working day already exists for {today}')

    def _create_loan_guarantors(self, members, loans):
        from apps.loans.models import LoanGuarantor

        count = 0
        for loan in loans:
            if loan.status in ('approved', 'disbursed', 'npa'):
                # Pick 2 guarantors from other members who are not the loan member
                guarantors = [m for m in members if m != loan.member][:2]
                for g in guarantors:
                    _, created = LoanGuarantor.objects.get_or_create(
                        loan=loan,
                        guarantor_member=g,
                        defaults={
                            'guarantee_amount': loan.approved_amount / 2
                            if loan.approved_amount
                            else loan.applied_amount / 2,
                        },
                    )
                    if created:
                        count += 1
        self.stdout.write(f'  {count} loan guarantors')

    def _create_member_nominees(self, members):
        from apps.members.models import MemberNominee

        count = 0
        nominee_data = [
            ('Nominee One', 'spouse', 50),
            ('Nominee Two', 'son', 30),
            ('Nominee Three', 'daughter', 20),
        ]
        for i, member in enumerate(members[:5]):
            for j, (name, relation, pct) in enumerate(nominee_data[: 2 if i % 2 == 0 else 1]):
                _, created = MemberNominee.objects.get_or_create(
                    member=member,
                    name=f'{name} of {member.name}',
                    defaults={
                        'relation': relation,
                        'share_percentage': Decimal(str(pct if j == 0 else 100 - nominee_data[0][2])),
                        'is_primary': j == 0,
                    },
                )
                if created:
                    count += 1
        self.stdout.write(f'  {count} member nominees')

    def _create_agent_collections(self, admin):
        from apps.agents.models import Agent, PigmmyAccount
        from apps.agents.services import record_agent_collection

        agents = Agent.objects.filter(status='active')
        count = 0
        today = date.today()
        for agent in agents:
            accounts = PigmmyAccount.objects.filter(agent=agent, status='active')
            if not accounts.exists():
                continue
            for day_offset in range(3):
                collection_date = today - timedelta(days=day_offset)
                payments = []
                for acc in accounts:
                    payments.append(
                        {
                            'account_id': acc.pk,
                            'amount': float(acc.installment_amount),
                        }
                    )
                try:
                    record_agent_collection(
                        agent=agent,
                        collection_date=collection_date,
                        client_payments=payments,
                        branch=agent.branch,
                        created_by=admin,
                    )
                    count += 1
                except (ValueError, Exception):
                    pass
        self.stdout.write(f'  {count} agent collections')
