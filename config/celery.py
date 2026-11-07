import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')

app = Celery('society_software')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'daily-day-end-processing': {
        'task': 'apps.dayend.tasks.run_all_day_end',
        'schedule': crontab(hour=23, minute=30),
    },
    'emi-due-reminders': {
        'task': 'apps.notifications.tasks.send_emi_reminders',
        'schedule': crontab(hour=9, minute=0),
    },
    'fd-maturity-alerts': {
        'task': 'apps.notifications.tasks.send_fd_maturity_alerts',
        'schedule': crontab(hour=10, minute=0),
    },
}
