from django.core.management.base import BaseCommand
from django.conf import settings

from redis import Redis
from libs.constants import TASK_IDENTITY_PREFIX  # noqa: E402


class Command(BaseCommand):
    help = 'Flushes task locks with the given prefix from the message broker'

    def add_arguments(self, parser):
        parser.add_argument(
            '--prefix',
            default=TASK_IDENTITY_PREFIX,
            help='Prefix of the locks to flush')
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show actions to perform without changing anything.')

    def handle(self, *args, **options):
        prefix = options['prefix']
        dry_run = options['dry_run']
        redis_client = Redis.from_url(settings.CELERY_BROKER_URL)

        # Retrieve all keys with the given prefix
        # the `lock:` pattern is prepended by python-redis-lock by default
        keys = redis_client.keys(f'lock:{prefix}*')

        if keys:
            if dry_run:
                self.stdout.write('Dry run mode, will delete following keys:')
                self.stdout.write(
                    '\n'.join(map(lambda k: k.decode('utf-8'), keys)))
            else:
                redis_client.delete(*keys)
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully flushed {len(keys)} locks.')
                )
        else:
            self.stdout.write('No locks found with the given prefix.')
