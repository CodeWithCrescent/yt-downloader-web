"""Time-limited file delivery helpers (UUID URLs, TTL cleanup)."""
import logging
import os
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def delivery_ttl_delta():
    return timedelta(minutes=getattr(settings, 'DELIVERY_TTL_MINUTES', 5))


def file_delivery_available(obj):
    """True if the packaged file can still be streamed."""
    if not obj or not obj.delivery_token:
        return False
    path = (obj.temp_file_path or '').strip()
    if not path or not os.path.isfile(path):
        return False
    if obj.file_ready_at is None:
        return False
    if timezone.now() - obj.file_ready_at > delivery_ttl_delta():
        return False
    try:
        return os.path.getsize(path) > 0
    except OSError:
        return False


def clear_delivery_fields(instance):
    instance.temp_file_path = ''
    instance.delivery_filename = ''
    instance.delivery_token = None
    instance.file_ready_at = None


def run_purge_expired_deliveries():
    """
    Delete packaged files older than DELIVERY_TTL_MINUTES and clear delivery fields.
    Called from Celery Beat and optionally `./manage.py purge_delivery_files`.
    """
    from .models import MediaDownload

    cutoff = timezone.now() - delivery_ttl_delta()
    qs = MediaDownload.objects.filter(
        file_ready_at__isnull=False,
        file_ready_at__lt=cutoff,
    ).exclude(temp_file_path='')
    removed = 0
    for obj in qs.iterator(chunk_size=100):
        path = (obj.temp_file_path or '').strip()
        if path and os.path.isfile(path):
            try:
                os.remove(path)
                logger.info('Removed expired delivery file: %s', path)
            except OSError as e:
                logger.warning('Could not remove %s: %s', path, e)
        MediaDownload.objects.filter(pk=obj.pk).update(
            temp_file_path='',
            delivery_filename='',
            delivery_token=None,
            file_ready_at=None,
        )
        removed += 1
    return removed
