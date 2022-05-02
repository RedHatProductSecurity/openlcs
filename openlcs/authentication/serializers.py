from rest_framework import serializers
from django.contrib.auth import get_user_model


class UserSerializer(serializers.ModelSerializer):
    """
    User Serializer
    """
    realname = serializers.CharField(source='profile.realname')
    manager = serializers.CharField(source='profile.manager.username')

    class Meta:
        model = get_user_model()
        fields = ('username', 'email', 'realname', 'manager')
