import json

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class TaskMeta(models.Model):
    task_id = models.CharField(max_length=155, unique=True)
    status = models.CharField('state', max_length=50)
    result = models.BinaryField(null=True, default=None, editable=False)
    date_done = models.DateTimeField('date_done', auto_now=True, null=True)
    traceback = models.TextField('traceback', blank=True, null=True)

    class Meta:
        db_table = 'celery_taskmeta'
        app_label = 'tasks'
        managed = False


class TaskManager(models.Manager):

    def create(self, *args, **kwargs):
        params = kwargs.get('params', None)
        if params and isinstance(params, dict):
            kwargs['params'] = json.dumps(params)
        return super(TaskManager, self).create(*args, **kwargs)


class Task(models.Model):
    owner = models.ForeignKey(
        get_user_model(),
        related_name='tasks',
        on_delete=models.CASCADE
    )
    meta_id = models.TextField(unique=True)
    params = models.TextField()
    task_flow = models.TextField()
    retries = models.IntegerField(default=0)
    content_type = models.ForeignKey(
        ContentType,
        blank=True, null=True,
        on_delete=models.CASCADE
    )
    parent_task_id = models.TextField(blank=True, default='')
    object_id = models.PositiveIntegerField(blank=True, null=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    objects = TaskManager()

    def __str__(self):
        return str(self.pk)

    class Meta:
        app_label = 'tasks'

    def save(self, *args, **kwargs):
        params = kwargs.get('params')
        if params and isinstance(params, dict):
            kwargs['params'] = json.dumps(params)
        super(Task, self).save(*args, **kwargs)

    def get_params(self):
        try:
            return json.loads(self.params)
        except Exception:
            return self.params
