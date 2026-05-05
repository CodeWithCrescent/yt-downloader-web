from django.core.management.base import BaseCommand

from downloader.delivery import run_purge_expired_deliveries


class Command(BaseCommand):
    help = 'Delete packaged files older than DELIVERY_TTL_MINUTES and clear delivery tokens.'

    def handle(self, *args, **options):
        n = run_purge_expired_deliveries()
        self.stdout.write(self.style.SUCCESS('Purged %s expired delivery record(s).' % n))
