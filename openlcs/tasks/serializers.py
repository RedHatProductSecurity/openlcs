from rest_framework import serializers

from tasks.models import Task


class TaskSerializer(serializers.ModelSerializer):
    """
    Task Serializer
    """
    owner = serializers.StringRelatedField()

    class Meta:
        model = Task
        fields = ('id', 'meta_id', 'owner', 'params', 'logs')
