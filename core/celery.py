import os
from celery import Celery
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('core')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

if getattr(settings, 'CELERY_BEAT_SCHEDULE', None):
    app.conf.beat_schedule = settings.CELERY_BEAT_SCHEDULE
