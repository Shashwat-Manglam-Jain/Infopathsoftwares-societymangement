from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django_tenants.utils import tenant_context

from apps.tenants.models import Domain, Society, Subscription, SubscriptionPlan

MEMBERS_HO = [
    {
        'no': 'M001',
        'name': 'Rajesh Kumar',
        'phone': '9876500001',
        'occupation': 'Agent',
        'gender': 'male',
        'city': 'Pune',
    },
    {
        'no': 'M002',
        'name': 'Sunil Patil',
        'phone': '9876500002',
        'occupation': 'Agent',
        'gender': 'male',
        'city': 'Pune',
    },
    {
        'no': 'M003',
        'name': 'Anita Deshmukh',
        'phone': '9876500003',
        'occupation': 'Teacher',
        'gender': 'female',
        'city': 'Pune',
    },
    {
        'no': 'M004',
        'name': 'Vikram Jadhav',
        'phone': '9876500004',
        'occupation': 'Farmer',
        'gender': 'male',
        'city': 'Pune',
    },
    {
        'no': 'M005',
        'name': 'Priya Kulkarni',
        'phone': '9876500005',
        'occupation': 'Shopkeeper',
        'gender': 'female',
        'city': 'Pune',
    },
    {
        'no': 'M006',
        'name': 'Manoj Shinde',
        'phone': '9876500006',
        'occupation': 'Worker',
        'gender': 'male',
        'city': 'Pune',
    },
    {
        'no': 'M007',
        'name': 'Sanjay Wagh',
        'phone': '9876500007',
        'occupation': 'Driver',
        'gender': 'male',
        'city': 'Pune',
    },
    {
        'no': 'M008',
        'name': 'Kavita More',
        'phone': '9876500008',
        'occupation': 'Tailor',
        'gender': 'female',
        'city': 'Pune',
    },
    {
        'no': 'M009',
        'name': 'Ramesh Gaikwad',
        'phone': '9876500009',
        'occupation': 'Carpenter',
        'gender': 'male',
        'city': 'Pune',
    },
    {
        'no': 'M010',
        'name': 'Sunita Pawar',
        'phone': '9876500010',
        'occupation': 'Nurse',
        'gender': 'female',
        'city': 'Pune',
    },
]

MEMBERS_BR = [
    {
        'no': 'M011',
        'name': 'Amit Sharma',
        'phone': '9876500011',
        'occupation': 'Agent',
        'gender': 'male',
        'city': 'Katol',
    },
    {
        'no': 'M012',
        'name': 'Deepak Thakur',
        'phone': '9876500012',
        'occupation': 'Farmer',
        'gender': 'male',
        'city': 'Katol',
    },
    {
        'no': 'M013',
        'name': 'Meena Raut',
        'phone': '9876500013',
        'occupation': 'Teacher',
        'gender': 'female',
        'city': 'Katol',
    },
    {
        'no': 'M014',
        'name': 'Nilesh Bhosle',
        'phone': '9876500014',
        'occupation': 'Shopkeeper',
        'gender': 'male',
        'city': 'Katol',
    },
    {
        'no': 'M015',
        'name': 'Pooja Yadav',
        'phone': '9876500015',
        'occupation': 'Worker',
        'gender': 'female',
        'city': 'Katol',
    },
    {
        'no': 'M016',
        'name': 'Sachin Kale',
        'phone': '9876500016',
        'occupation': 'Mechanic',
        'gender': 'male',
        'city': 'Katol',
    },
    {
        'no': 'M017',
        'name': 'Rekha Deshpande',
        'phone': '9876500017',
        'occupation': 'Nurse',
        'gender': 'female',
        'city': 'Katol',
    },
    {
        'no': 'M018',
        'name': 'Ganesh Chavan',
        'phone': '9876500018',
        'occupation': 'Driver',
        'gender': 'male',
        'city': 'Katol',
    },
]

USERS = [
    {'username': 'ho_manager', 'first_name': 'HO', 'last_name': 'Manager', 'role': 'branch_manager', 'branch': 'HO'},
    {'username': 'ho_cashier', 'first_name': 'HO', 'last_name': 'Cashier', 'role': 'cashier', 'branch': 'HO'},
    {'username': 'ho_accountant', 'first_name': 'HO', 'last_name': 'Accountant', 'role': 'accountant', 'branch': 'HO'},
    {'username': 'ho_auditor', 'first_name': 'HO', 'last_name': 'Auditor', 'role': 'auditor', 'branch': 'HO'},
    {
        'username': 'br_manager',
        'first_name': 'BR01',
        'last_name': 'Manager',
        'role': 'branch_manager',
        'branch': 'BR01',
    },
    {'username': 'br_cashier', 'first_name': 'BR01', 'last_name': 'Cashier', 'role': 'cashier', 'branch': 'BR01'},
]

AGENTS = [
    {
        'code': 'AG0001',
        'member_no': 'M001',
        'branch': 'HO',
        'phone': '9876500001',
        'area': 'Pune Station Area',
        'commission': '2.00',
    },
    {
        'code': 'AG0002',
        'member_no': 'M002',
        'branch': 'HO',
        'phone': '9876500002',
        'area': 'Kothrud Area',
        'commission': '2.50',
    },
    {
        'code': 'AG0003',
        'member_no': 'M011',
        'branch': 'BR01',
        'phone': '9876500011',
        'area': 'Katol Market',
        'commission': '2.00',
    },
]

PIGMMY_CLIENTS = [
    # AG0001 clients (HO) — daily ₹100
    {'agent': 'AG0001', 'member_no': 'M003', 'type': 'daily', 'amount': '100.00', 'months': 12, 'rate': '6.00'},
    {'agent': 'AG0001', 'member_no': 'M004', 'type': 'daily', 'amount': '100.00', 'months': 12, 'rate': '6.00'},
    {'agent': 'AG0001', 'member_no': 'M005', 'type': 'daily', 'amount': '100.00', 'months': 12, 'rate': '6.00'},
    {'agent': 'AG0001', 'member_no': 'M006', 'type': 'daily', 'amount': '100.00', 'months': 12, 'rate': '6.00'},
    # AG0002 clients (HO) — mixed
    {'agent': 'AG0002', 'member_no': 'M007', 'type': 'daily', 'amount': '200.00', 'months': 12, 'rate': '6.00'},
    {'agent': 'AG0002', 'member_no': 'M008', 'type': 'daily', 'amount': '200.00', 'months': 12, 'rate': '6.00'},
    {'agent': 'AG0002', 'member_no': 'M009', 'type': 'monthly', 'amount': '5000.00', 'months': 24, 'rate': '7.00'},
    {'agent': 'AG0002', 'member_no': 'M010', 'type': 'monthly', 'amount': '5000.00', 'months': 24, 'rate': '7.00'},
    # AG0003 clients (BR01) — daily ₹150
    {'agent': 'AG0003', 'member_no': 'M015', 'type': 'daily', 'amount': '150.00', 'months': 12, 'rate': '6.00'},
    {'agent': 'AG0003', 'member_no': 'M016', 'type': 'daily', 'amount': '150.00', 'months': 12, 'rate': '6.00'},
    {'agent': 'AG0003', 'member_no': 'M017', 'type': 'daily', 'amount': '150.00', 'months': 12, 'rate': '6.00'},
]


class Command(BaseCommand):
    help = 'Create demo tenant with comprehensive test data for all modules'

    def add_arguments(self, parser):
        parser.add_argument(
            '--domain',
            type=str,
            default='demo.localhost',
            help='Domain for the demo tenant (default: demo.localhost)',
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing demo tenant and recreate from scratch',
        )

    def handle(self, *args, **options):
        domain_name = options['domain']

        SubscriptionPlan.objects.update_or_create(
            name='Basic',
            defaults={
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
        )

        plan, _ = SubscriptionPlan.objects.update_or_create(
            name='Professional',
            defaults={
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
        )

        SubscriptionPlan.objects.update_or_create(
            name='Enterprise',
            defaults={
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
        )

        existing = Society.objects.filter(schema_name='demo').first()
        if existing:
            if options['reset']:
                self.stdout.write(self.style.WARNING('Deleting existing demo tenant (dropping schema)...'))
                from django.db import connection

                with connection.cursor() as cursor:
                    cursor.execute('DROP SCHEMA IF EXISTS demo CASCADE')
                existing.delete()
            else:
                self.stdout.write(self.style.WARNING('Demo tenant already exists. Use --reset to recreate.'))
                return

        self.stdout.write('Creating demo society...')
        society = Society.objects.create(
            schema_name='demo',
            name='Demo Credit Cooperative Society',
            registration_no='DEMO-2026-001',
            registration_date=date(2020, 1, 1),
            address='123 Demo Street, Shivaji Nagar',
            city='Pune',
            state='Maharashtra',
            pincode='411001',
            phone='9876543210',
            email='admin@demo-society.com',
            society_type='credit_cooperative',
        )

        Domain.objects.create(domain=domain_name, tenant=society, is_primary=True)

        Subscription.objects.create(
            society=society,
            plan=plan,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365),
            is_trial=True,
            status='trial',
        )

        with tenant_context(society):
            self._setup_all(society)

        self.stdout.write(
            self.style.SUCCESS(
                f'\nDemo tenant ready: {domain_name}\n'
                f'  Admin login: admin / admin123\n'
                f'  HO staff: ho_manager, ho_cashier, ho_accountant, ho_auditor / test123\n'
                f'  BR01 staff: br_manager, br_cashier / test123\n'
                f'  Agents: AG0001 (4 clients), AG0002 (4 clients) at HO; AG0003 (3 clients) at BR01'
            )
        )

    def _setup_all(self, society):
        from apps.accounting.initial_coa import setup_chart_of_accounts
        from apps.accounts.models import CustomUser
        from apps.branches.models import Branch
        from apps.dayend.models import FinancialYear

        # --- Branches ---
        self.stdout.write('  Creating branches...')
        ho = Branch.objects.create(
            branch_code='HO',
            branch_name='Head Office',
            address='123 Demo Street, Shivaji Nagar',
            city='Pune',
            state='Maharashtra',
            pincode='411001',
            phone='9876543210',
            is_head_office=True,
            opening_date=date(2020, 1, 1),
            status='active',
        )
        br01 = Branch.objects.create(
            branch_code='BR01',
            branch_name='Katol Branch',
            address='45 Market Road',
            city='Katol',
            state='Maharashtra',
            pincode='441302',
            phone='9876543211',
            is_head_office=False,
            opening_date=date(2023, 4, 1),
            status='active',
        )
        branches = {'HO': ho, 'BR01': br01}

        # --- Financial Year ---
        fy_start = date(date.today().year, 4, 1)
        if date.today().month < 4:
            fy_start = date(date.today().year - 1, 4, 1)
        fy_end = date(fy_start.year + 1, 3, 31)
        FinancialYear.objects.create(
            fy_code=f'{fy_start.year}-{str(fy_end.year)[-2:]}',
            start_date=fy_start,
            end_date=fy_end,
            is_current=True,
        )

        # --- Chart of Accounts ---
        self.stdout.write('  Setting up chart of accounts...')
        setup_chart_of_accounts(branches=[ho, br01])

        # --- Admin User ---
        admin = CustomUser.objects.create_superuser(
            username='admin',
            email='admin@demo-society.com',
            password='admin123',
            phone='9876543210',
            role='admin',
            branch=ho,
            can_access_all_branches=True,
        )

        # --- Staff Users ---
        self.stdout.write('  Creating staff users...')
        for u in USERS:
            CustomUser.objects.create_user(
                username=u['username'],
                password='test123',
                first_name=u['first_name'],
                last_name=u['last_name'],
                email=f'{u["username"]}@demo-society.com',
                role=u['role'],
                branch=branches[u['branch']],
                can_access_all_branches=(u['role'] == 'admin'),
            )

        # --- Share Config ---
        from apps.shares.models import ShareConfig, ShareHolding

        ShareConfig.objects.create(
            face_value_per_share=Decimal('100.00'),
            max_shares_per_member=100,
            min_shares_required=1,
            dividend_rate=Decimal('12.00'),
            is_active=True,
        )

        # --- Members ---
        self.stdout.write('  Creating members...')
        from apps.members.models import Member

        member_objs = {}
        for m_data in MEMBERS_HO:
            member = Member.objects.create(
                member_no=m_data['no'],
                branch=ho,
                name=m_data['name'],
                phone=m_data['phone'],
                occupation=m_data['occupation'],
                gender=m_data['gender'],
                city=m_data['city'],
                state='Maharashtra',
                join_date=date(2024, 4, 1),
                status='active',
                category='A',
                dob=date(1985, 6, 15),
            )
            member_objs[m_data['no']] = member
        for m_data in MEMBERS_BR:
            member = Member.objects.create(
                member_no=m_data['no'],
                branch=br01,
                name=m_data['name'],
                phone=m_data['phone'],
                occupation=m_data['occupation'],
                gender=m_data['gender'],
                city=m_data['city'],
                state='Maharashtra',
                join_date=date(2024, 4, 1),
                status='active',
                category='A',
                dob=date(1988, 3, 20),
            )
            member_objs[m_data['no']] = member

        # --- Share Holdings ---
        self.stdout.write('  Creating share holdings...')
        for mno, member in member_objs.items():
            ShareHolding.objects.create(
                member=member,
                branch=member.branch,
                share_count=10,
                face_value_per_share=Decimal('100.00'),
                total_amount=Decimal('1000.00'),
                purchase_date=member.join_date,
                certificate_no=f'SH-{mno}',
                status='active',
                created_by=admin,
            )

        # --- Savings Accounts (auto-generates account_no via model save) ---
        self.stdout.write('  Creating savings accounts...')
        from apps.accounting.models import ChartOfAccounts
        from apps.savings.models import SavingsAccount

        savings_head = ChartOfAccounts.objects.filter(related_table_name='saving').first()
        security_head = (
            ChartOfAccounts.objects.filter(
                related_table_name='security',
                name__icontains='security deposit',
            )
            .exclude(name__icontains='agent')
            .first()
        )

        savings_objs = {}
        for mno, member in member_objs.items():
            sa = SavingsAccount.objects.create(
                member=member,
                branch=member.branch,
                account_type='savings',
                gl_head=savings_head,
                opening_date=member.join_date,
                status='active',
                current_balance=Decimal('5000.00'),
                interest_rate=Decimal('4.00'),
                created_by=admin,
            )
            savings_objs[mno] = sa

        # --- Security Deposit accounts for agent members ---
        self.stdout.write('  Creating security deposit accounts for agents...')
        agent_member_nos = ['M001', 'M002', 'M011']
        security_objs = {}
        for mno in agent_member_nos:
            member = member_objs[mno]
            sd = SavingsAccount.objects.create(
                member=member,
                branch=member.branch,
                account_type='security',
                gl_head=security_head,
                opening_date=member.join_date,
                status='active',
                current_balance=Decimal('10000.00'),
                created_by=admin,
            )
            security_objs[mno] = sd

        # --- Agents ---
        self.stdout.write('  Creating agents...')
        from apps.agents.models import Agent

        agent_objs = {}
        for a_data in AGENTS:
            mno = a_data['member_no']
            agent = Agent.objects.create(
                agent_code=a_data['code'],
                member=member_objs[mno],
                branch=branches[a_data['branch']],
                savings_account=savings_objs[mno],
                security_deposit_account=security_objs[mno],
                security_deposit_amount=Decimal('10000.00'),
                commission_rate=Decimal(a_data['commission']),
                joining_date=date(2024, 5, 1),
                phone=a_data['phone'],
                area=a_data['area'],
                status='active',
                created_by=admin,
            )
            agent_objs[a_data['code']] = agent
            self.stdout.write(f'    {a_data["code"]}: {member_objs[mno].name} ({a_data["branch"]})')

        # --- Pigmmy Accounts ---
        self.stdout.write('  Creating pigmmy accounts...')
        from apps.agents.services import create_pigmmy_account

        for pc in PIGMMY_CLIENTS:
            agent = agent_objs[pc['agent']]
            member = member_objs[pc['member_no']]
            linked_savings = savings_objs[pc['member_no']]
            try:
                acct = create_pigmmy_account(
                    member=member,
                    agent=agent,
                    branch=member.branch,
                    installment_amount=Decimal(pc['amount']),
                    deposit_period_months=pc['months'],
                    interest_rate=Decimal(pc['rate']),
                    deposit_type=pc['type'],
                    linked_savings=linked_savings,
                    created_by=admin,
                )
                self.stdout.write(
                    f'    {acct.account_no}: {member.name} -> {pc["agent"]} ({pc["type"]} ₹{pc["amount"]})'
                )
            except ValueError as e:
                self.stdout.write(self.style.ERROR(f'    FAILED {pc["member_no"]}: {e}'))

        self.stdout.write(self.style.SUCCESS('  All test data created successfully!'))
