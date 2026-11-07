import logging
from datetime import timedelta

from celery import shared_task
from django_tenants.utils import tenant_context

from apps.tenants.models import Society

logger = logging.getLogger(__name__)


@shared_task
def send_emi_reminders():
    for society in Society.objects.filter(is_active=True):
        with tenant_context(society):
            _send_emi_reminders_for_tenant()


def _send_emi_reminders_for_tenant():
    from django.utils import timezone

    from apps.loans.models import EMISchedule

    from .services import send_emi_reminder

    tomorrow = timezone.now().date() + timedelta(days=1)
    upcoming = EMISchedule.objects.filter(
        due_date=tomorrow,
        status='pending',
        loan__status='active',
    ).select_related('loan__member')

    for emi in upcoming:
        loan = emi.loan
        try:
            send_emi_reminder(loan.member, loan.loan_no, emi.amount, emi.due_date)
        except Exception:
            logger.exception('Failed EMI reminder for %s', loan.loan_no)


@shared_task
def send_fd_maturity_alerts():
    for society in Society.objects.filter(is_active=True):
        with tenant_context(society):
            _send_fd_maturity_alerts_for_tenant()


def _send_fd_maturity_alerts_for_tenant():
    from django.utils import timezone

    from apps.deposits.models import FixedDeposit

    from .services import send_fd_maturity_alert

    week_ahead = timezone.now().date() + timedelta(days=7)
    maturing = FixedDeposit.objects.filter(
        maturity_date=week_ahead,
        status='active',
    ).select_related('member')

    for fd in maturing:
        try:
            send_fd_maturity_alert(fd.member, fd.fd_no, fd.maturity_date, fd.maturity_amount)
        except Exception:
            logger.exception('Failed FD maturity alert for %s', fd.fd_no)
