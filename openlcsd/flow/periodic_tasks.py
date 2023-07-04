from openlcsd.celery import app
from openlcs.libs.celery_helper import generate_priority_kwargs


@app.task(bind=True)
def test_task(self, *args, **kwargs):
    print("test task")


@app.task(bind=True)
def print_task_id(self, *args, **kwargs):
    print(f"task_id:{self.request.id}")


@app.task(bind=True)
def run_corgi_sync(self, **kwargs):
    flow = "flow.tasks.flow_get_active_subscriptions"
    app.send_task(flow, [kwargs], **generate_priority_kwargs("high"))


@app.task(bind=True)
def clean_unused_shared_remote_source(self, **kwargs):
    flow = "flow.tasks.flow_clean_unused_shared_remote_source"
    app.send_task(flow, [kwargs], **generate_priority_kwargs("low"))
