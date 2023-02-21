from django.core.management.base import BaseCommand
from django_celery_beat.models import (
    CrontabSchedule,
    PeriodicTask,
)


class Command(BaseCommand):
    help = 'Load/create pre-defined periodic tasks for beat service'

    def add_arguments(self, parser):
        # FIXME: allow to specify `task` explicitly instead of using
        # `name` for `task`.
        parser.add_argument(
            '--name',
            type=str,
            default='openlcsd.flow.periodic_tasks.print_task_id',
            help='Specifies the name of the task'
        )
        parser.add_argument(
            '--interval',
            type=str,
            choices=['daily', 'hourly', 'minutely'],
            default='daily',
            help='Specifies the interval of the import'
        )

    def handle(self, *args, **options):
        module_name = options['name']
        interval = options['interval']
        verbosity = options['verbosity']

        interval_map = {
            'daily': {'minute': '30', 'hour': '0'},
            'hourly': {'minute': '0'},
            'minutely': {}
        }

        minute = interval_map[interval].get("minute", "*")
        hour = interval_map[interval].get("hour", "*")

        crontab_schedule, _ = CrontabSchedule.objects.get_or_create(
            minute=minute,
            hour=hour,
            day_of_week='*',
            day_of_month='*',
            month_of_year='*'
        )
        periodic_task, created = PeriodicTask.objects.update_or_create(
            name=module_name,
            task=module_name,
            defaults={
                'crontab': crontab_schedule,
                'enabled': True,
                'args': '()',
                'kwargs': '{}',
            }
        )

        if verbosity >= 1:
            if created:
                msg = f'Periodic task "{module_name}"({interval}) created.'
            else:
                msg = f'Periodic task "{module_name}({interval})" updated.'
            self.stdout.write(msg)
