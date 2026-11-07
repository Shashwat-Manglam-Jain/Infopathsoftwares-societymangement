from celery import shared_task
from django_tenants.utils import tenant_context

from apps.tenants.models import Society


@shared_task
def run_all_day_end():
    for society in Society.objects.filter(is_active=True):
        run_society_day_end.delay(society.schema_name)


@shared_task
def run_society_day_end(schema_name):
    from django.utils import timezone

    from apps.branches.models import Branch

    from .models import DayEndLog

    society = Society.objects.get(schema_name=schema_name)
    with tenant_context(society):
        today = timezone.now().date()
        for branch in Branch.objects.filter(status='active'):
            if DayEndLog.objects.filter(
                branch=branch,
                processing_date=today,
                status='completed',
            ).exists():
                continue
            run_branch_day_end.delay(branch.id)


@shared_task
def run_branch_day_end(branch_id):
    from apps.branches.models import Branch

    from .services import run_day_end

    branch = Branch.objects.get(id=branch_id)
    run_day_end(branch, user=None)
