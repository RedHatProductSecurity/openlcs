from rest_framework import serializers

from packages.models import File
from reports.models import LicenseDetection


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
