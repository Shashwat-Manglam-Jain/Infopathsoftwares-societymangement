from django.core.management.base import BaseCommand
from django_tenants.utils import tenant_context

from apps.tenants.models import Society


class Command(BaseCommand):
    help = 'Set up Chart of Accounts for tenants that are missing it.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--schema',
            help='Only run for a specific tenant schema name',
        )

    def handle(self, *args, **options):
        from apps.accounting.initial_coa import setup_chart_of_accounts
        from apps.accounting.models import ChartOfAccounts
        from apps.branches.models import Branch

        tenants = Society.objects.exclude(schema_name='public')
        if options['schema']:
            tenants = tenants.filter(schema_name=options['schema'])

        for tenant in tenants:
            with tenant_context(tenant):
                count = ChartOfAccounts.objects.count()
                if count > 0:
                    self.stdout.write(f'{tenant.schema_name}: already has {count} GL heads, skipping')
                    continue

                branches = list(Branch.objects.all())
                if not branches:
                    self.stdout.write(self.style.WARNING(f'{tenant.schema_name}: no branches found, skipping'))
                    continue

                setup_chart_of_accounts(branches=branches)
                new_count = ChartOfAccounts.objects.count()
                self.stdout.write(self.style.SUCCESS(f'{tenant.schema_name}: created {new_count} GL heads'))
