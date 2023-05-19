from celery import Celery
from celery import signals
from celery.signals import celeryd_init
from celery.signals import worker_process_shutdown
from redis import Redis

from openlcs.libs.constants import TASK_IDENTITY_PREFIX

from . import celeryconfig

app = Celery('openlcsd')

app.config_from_object(celeryconfig)


def task_success_handler(*args, **kwargs):
    pass


def task_failure_handler(*args, **kwargs):
    pass


def enable_signals():
    signals.task_success.connect(task_success_handler)
    signals.task_failure.connect(task_failure_handler)


def remove_stale_redis_locks():
    redis_client = Redis.from_url(celeryconfig.broker_url)
    keys = redis_client.keys(f"lock:{TASK_IDENTITY_PREFIX}*")
    # There are chances when keys are empty
    if keys:
        redis_client.delete(*keys)


@celeryd_init.connect
def on_celeryd_init(sender, **kwargs):
    enable_signals()


@worker_process_shutdown.connect
def on_worker_process_shutdown(sender, **kwargs):
    remove_stale_redis_locks()
