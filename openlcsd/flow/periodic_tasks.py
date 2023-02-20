from openlcsd.celery import app


@app.task(bind=True)
def test_task(self, *args, **kwargs):
    print("test task")


@app.task(bind=True)
def print_task_id(self, *args, **kwargs):
    print(f"task_id:{self.request.id}")
