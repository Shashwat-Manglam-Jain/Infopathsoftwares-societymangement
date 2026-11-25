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
        parser.add_argument(
            '--force',
            action='store_true',
            help='Update existing heads to match current defaults (use after adding new heads)',
        )

    def handle(self, *args, **options):
        from apps.accounting.initial_coa import setup_chart_of_accounts
        from apps.accounting.models import ChartOfAccounts
        from apps.branches.models import Branch

        force = options['force']
        tenants = Society.objects.exclude(schema_name='public')
        if options['schema']:
            tenants = tenants.filter(schema_name=options['schema'])

        for tenant in tenants:
            with tenant_context(tenant):
                count = ChartOfAccounts.objects.count()
                if count > 0 and not force:
                    self.stdout.write(
                        f'{tenant.schema_name}: already has {count} GL heads, skipping (use --force to update)'
                    )
                    continue

                branches = list(Branch.objects.all())
                if not branches:
                    self.stdout.write(self.style.WARNING(f'{tenant.schema_name}: no branches found, skipping'))
                    continue

                setup_chart_of_accounts(branches=branches, force=force)
                new_count = ChartOfAccounts.objects.count()
                verb = 'updated' if force and count > 0 else 'created'
                self.stdout.write(self.style.SUCCESS(f'{tenant.schema_name}: {verb} {new_count} GL heads'))
