from rest_framework import serializers

from tasks.models import Task, TaskMeta


class TaskSerializer(serializers.ModelSerializer):
    """
    Task Serializer
    """
    owner = serializers.StringRelatedField()
    status = serializers.SerializerMethodField()
    date_done = serializers.SerializerMethodField()
    traceback = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = ('id', 'meta_id', 'owner', 'params',
                  'status', 'date_done', 'traceback')

    def get_status(self, obj):
        return TaskMeta.objects.get(task_id=obj.meta_id).status

    def get_date_done(self, obj):
        return TaskMeta.objects.get(task_id=obj.meta_id).date_done

    def get_traceback(self, obj):
        return TaskMeta.objects.get(task_id=obj.meta_id).traceback
