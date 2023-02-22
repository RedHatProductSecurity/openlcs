from openlcsd.celery import app


@app.task(bind=True)
def test_task(self, *args, **kwargs):
    print("test task")


@app.task(bind=True)
def print_task_id(self, *args, **kwargs):
    print(f"task_id:{self.request.id}")


@app.task(bind=True)
def run_corgi_sync(self, **kwargs):
    print(f"task_id:{self.request.id}")
    flow = "flow.tasks.flow_get_corgi_components"
    # The keyword arguments are not used right now.
    app.send_task(flow, [kwargs])
