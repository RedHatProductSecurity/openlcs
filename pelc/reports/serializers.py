from rest_framework import serializers

from packages.models import File
from reports.models import LicenseDetection
from reports.models import CopyrightDetection


class LicenseDetectionSerializer(serializers.ModelSerializer):
    """
    LicenseDetection serializer.
    """
    file = serializers.SlugRelatedField(
        queryset=File.objects.all(),
        slug_field='swhid',
        allow_null=False,
        required=True
    )

    class Meta:
        model = LicenseDetection
        fields = "__all__"


class CopyrightDetectionSerializer(serializers.ModelSerializer):
    """
    CopyrightDetection serializer.
    """
    file = serializers.SlugRelatedField(
        queryset=File.objects.all(),
        slug_field='swhid',
        allow_null=False,
        required=True
    )

    class Meta:
        model = CopyrightDetection
        fields = "__all__"
