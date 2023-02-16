from openlcsd.celery import app

# test periodic tasks


@app.task(bind=True)
def test_task(self, *args, **kwargs):
    print("test task")


@app.task(bind=True)
def print_task_id(self, *args, **kwargs):
    print(f"task_id:{self.request.id}")


# TODO add periodic tasks
