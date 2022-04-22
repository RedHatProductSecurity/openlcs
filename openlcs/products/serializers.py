from rest_framework import serializers

from products.models import Release
from products.models import ReleasePackage


class ReleaseSerializer(serializers.ModelSerializer):
    """
    Release serializer.
    """

    class Meta:
        model = Release
        fields = "__all__"


class ReleasePackageSerializer(serializers.ModelSerializer):

    scan_result = serializers.SerializerMethodField()

    class Meta:
        model = ReleasePackage
        exclude = ('id', 'release',)

    def get_scan_result(self, obj):
        return obj.get_scan_result()
