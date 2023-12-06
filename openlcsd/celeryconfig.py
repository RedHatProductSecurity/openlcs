import os
# celery broker settings
broker_url = os.environ.get('CELERY_BROKER_URL',
                            'redis://localhost:6379/0')

# Access hub database from the worker nodes.
# Tasks state / result will be stored in below db.
result_backend = os.environ.get(
        'CELERY_RESULT_BACKEND',
        'db+postgresql://openlcs:redhat@127.0.0.1/openlcs')

task_serializer = 'json'
accept_content = ['json']
result_serializer = 'json'
result_expires = None

task_track_started = True

# Task hard time limit in seconds. The worker processing the task will
# be killed and  replaced with a new one when this is exceeded, the task
# will be marked as failed task.
task_time_limit = 432000

# Configure soft time limit a little earlier than hard time limit
# so that we get a chance to retry it before force stop it.
task_soft_time_limit = 430200

broker_transport_options = {
    'visibility_timeout': 86400,
    'priority_steps': [0, 1, 2],
    'sep': ':',
    'queue_order_strategy': 'priority',
}

# List of modules to import when celery starts.
imports = (
    'openlcsd.tasks',
    'openlcsd.flow.tasks',
    'openlcsd.flow.periodic_tasks'
)
