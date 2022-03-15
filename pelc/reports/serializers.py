from rest_framework import serializers

from reports.models import LicenseDetection
from reports.models import CopyrightDetection


class LicenseDetectionSerializer(serializers.ModelSerializer):
    """
    LicenseDetection serializer.
    """

    class Meta:
        model = LicenseDetection
        fields = "__all__"


class CopyrightDetectionSerializer(serializers.ModelSerializer):
    """
    CopyrightDetection serializer.
    """
    class Meta:
        model = CopyrightDetection
        fields = "__all__"
