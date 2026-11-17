from django.core.management.base import BaseCommand

from apps.tenants.models import Society


class Command(BaseCommand):
    help = 'Deactivate test/demo tenants so they do not appear in the public login dropdown'

    TEST_NAMES = [
        'Production Test Society',
        'Test Multi Client Society',
    ]

    def handle(self, *args, **options):
        qs = Society.objects.filter(name__in=self.TEST_NAMES, is_active=True)
        count = qs.count()
        if count == 0:
            self.stdout.write('No active test tenants found.')
            return
        qs.update(is_active=False)
        self.stdout.write(self.style.SUCCESS(f'Deactivated {count} test tenant(s).'))
