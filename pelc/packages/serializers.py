from rest_framework import serializers

from packages.models import File
from packages.models import Source
from packages.models import Path
from packages.models import Package

from libs.swh_tools import swhid_check


class FileSerializer(serializers.ModelSerializer):
    """
    File serializer.
    """
    def validate(self, attrs):
        attrs = super(FileSerializer, self).validate(attrs)
        swhid_check(attrs.get('swhid'))
        return attrs

    class Meta:
        model = File
        fields = "__all__"


class BulkFileSerializer(serializers.Serializer):
    """
    Bulk file serializer, use to return validate files after created.
    """
    files = FileSerializer(many=True)


class BulkCreateFileSerializer(serializers.Serializer):
    """
    Bulk create file serializer, use to validate request files data.
    """
    swhids = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=False
    )

    def validate(self, attrs):
        attrs = super(BulkCreateFileSerializer, self).validate(attrs)
        for swhid in attrs.get('swhids'):
            swhid_check(swhid)
        return attrs


class SourceSerializer(serializers.ModelSerializer):
    """
    Source serializer.
    """

    class Meta:
        model = Source
        fields = "__all__"


class PathSerializer(serializers.ModelSerializer):
    """
    Path serializer
    """
    source = serializers.SlugRelatedField(
        queryset=Source.objects.all(),
        slug_field='checksum',
        allow_null=False,
        required=True)
    file = serializers.SlugRelatedField(
        queryset=File.objects.all(),
        slug_field='swhid',
        allow_null=False,
        required=True)

    class Meta:
        model = Path
        fields = "__all__"


class BulkPathSerializer(serializers.Serializer):
    """
    Bulk path serializer, se to validate request paths data.
    """
    paths = PathSerializer(many=True)


class PackageSerializer(serializers.ModelSerializer):
    """
    Package serializer.
    """
    source = serializers.SlugRelatedField(
        queryset=Source.objects.all(),
        slug_field='checksum',
        allow_null=False,
        required=True)

    class Meta:
        model = Package
        fields = "__all__"
