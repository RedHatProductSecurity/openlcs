from celery import Celery
from celery import signals
from celery.signals import celeryd_init

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


@celeryd_init.connect
def on_celeryd_init(sender, **kwargs):
    enable_signals()
