from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django_tenants.utils import tenant_context

from apps.tenants.models import Domain, Society, Subscription, SubscriptionPlan


class Command(BaseCommand):
    help = 'Create a demo society with default data for testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--domain',
            type=str,
            default='demo.localhost',
            help='Domain for the demo tenant (default: demo.localhost)',
        )

    def handle(self, *args, **options):
        domain_name = options['domain']

        plan, _ = SubscriptionPlan.objects.get_or_create(
            name='Professional',
            defaults={
                'max_members': 1000,
                'max_branches': 5,
                'max_users': 10,
                'price_monthly': Decimal('5000.00'),
                'features': {
                    'savings': True,
                    'loans': True,
                    'fd': True,
                    'rd': True,
                    'sms': True,
                    'reports': True,
                },
                'is_active': True,
            },
        )

        if Society.objects.filter(schema_name='demo').exists():
            self.stdout.write(self.style.WARNING('Demo tenant already exists.'))
            return

        society = Society.objects.create(
            schema_name='demo',
            name='Demo Credit Cooperative Society',
            registration_no='DEMO-2026-001',
            registration_date=date(2020, 1, 1),
            address='123 Demo Street',
            city='Pune',
            state='Maharashtra',
            pincode='411001',
            phone='9876543210',
            email='admin@demo-society.com',
            society_type='credit_cooperative',
        )

        Domain.objects.create(
            domain=domain_name,
            tenant=society,
            is_primary=True,
        )

        Subscription.objects.create(
            society=society,
            plan=plan,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=90),
            is_trial=True,
            status='trial',
        )

        with tenant_context(society):
            from apps.branches.models import Branch

            ho = Branch.objects.create(
                branch_code='HO',
                branch_name='Head Office',
                address='123 Demo Street',
                city='Pune',
                state='Maharashtra',
                pincode='411001',
                phone='9876543210',
                is_head_office=True,
                opening_date=date(2020, 1, 1),
                status='active',
            )

            from apps.accounts.models import CustomUser

            CustomUser.objects.create_superuser(
                username='admin',
                email='admin@demo-society.com',
                password='admin123',
                phone='9876543210',
                role='super_admin',
                branch=ho,
                can_access_all_branches=True,
            )

            from apps.dayend.models import FinancialYear

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

            from apps.accounting.initial_coa import setup_chart_of_accounts

            setup_chart_of_accounts(branches=[ho])

        self.stdout.write(self.style.SUCCESS(f'Demo tenant created: {domain_name} (login: admin / admin123)'))
