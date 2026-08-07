import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.dev',)
app=Celery('config')
app.config_from_object('django.conf:settings',namespace='CELERY',)
app.autodiscover_tasks()
app.conf.beat_schedule={
    'send-weekly-digests':{
        'task':'tasks.tasks.send_all_weekly_digests',
        'schedule':crontab(
            hour=9,
            minute=0,
            day_of_week='monday',
        ),
    },
    'cleanup-old-exports':{
        'task':'common.tasks.cleanup_old_exports',
        'schedule':crontab(
            hour=3,
            minute=0,
        ),
    },
}
