from celery.states import SUCCESS
from django.urls import reverse
from django.conf import settings
from rest_framework import serializers

from tasks.models import Task, TaskMeta


class TaskSerializer(serializers.ModelSerializer):
    """
    Task Serializer
    """
    owner = serializers.StringRelatedField()
    date_done = serializers.SerializerMethodField()
    traceback = serializers.SerializerMethodField()
    object_url = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = ('id', 'meta_id', 'owner', 'params', 'status', 'date_done',
                  'traceback', 'object_url', 'parent_task_id')

    def get_date_done(self, obj):
        try:
            taskmeta = TaskMeta.objects.get(task_id=obj.meta_id)
        except TaskMeta.DoesNotExist:
            return None
        return taskmeta.date_done

    def get_traceback(self, obj):
        try:
            taskmeta = TaskMeta.objects.get(task_id=obj.meta_id)
        except TaskMeta.DoesNotExist:
            return None
        return taskmeta.traceback

    def get_object_url(self, obj):
        if obj.content_object is None:
            return obj.content_object

        try:
            taskmeta_obj = TaskMeta.objects.get(task_id=obj.meta_id)
        except TaskMeta.DoesNotExist:
            return None

        if taskmeta_obj.status == SUCCESS:
            return "http://{}{}".format(
                settings.HOSTNAME,
                reverse("sources-detail", args=[obj.content_object.id])
            )
        else:
            return None
