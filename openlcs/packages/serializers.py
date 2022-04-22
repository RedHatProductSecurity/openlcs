import copy
from rest_framework import serializers

from packages.models import File
from packages.models import Source
from packages.models import Package
from packages.models import Path
from products.models import Release
from tasks.models import Task

# pylint:disable=no-name-in-module,import-error
from openlcs.celery import app
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


class SourceSerializer(serializers.ModelSerializer):
    """
    Source serializer.
    """
    packages = PackageSerializer(many=True, read_only=True)
    license_detections = serializers.SerializerMethodField()
    copyright_detections = serializers.SerializerMethodField()

    class Meta:
        model = Source
        fields = "__all__"

    def get_license_detections(self, obj):
        license_keys = obj.get_license_detections().values_list(
                'license_key', flat=True)
        return license_keys.distinct()

    def get_copyright_detections(self, obj):
        copyrights = obj.get_copyright_detections().values_list(
                'statement', flat=True)
        return copyrights.distinct()


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
    Bulk file serializer, use to return validate paths after created.
    """
    paths = PathSerializer(many=True)


class CreatePathSerializer(serializers.Serializer):
    """
    Create path serializer, use to return validated paths data in paths list.
    """
    file = serializers.SlugRelatedField(
        queryset=File.objects.all(),
        slug_field='swhid',
        allow_null=False,
        required=True)
    path = serializers.CharField(required=True)


class BulkCreatePathSerializer(serializers.Serializer):
    """
    Bulk path serializer, use to validate request paths data.
    """
    source = serializers.SlugRelatedField(
        queryset=Source.objects.all(),
        slug_field='checksum',
        allow_null=False,
        required=True)
    paths = CreatePathSerializer(many=True)


def release_validator(value):
    """
    Check that the product release is in db.
    """
    if value is not None:
        try:
            Release.objects.get(name=value)
        except Release.DoesNotExist:
            err_msg = 'Non-existent product release: %s' % value
            raise serializers.ValidationError(err_msg) from None
    return value


class ImportSerializer(serializers.Serializer):
    def get_task_flow(self):
        return 'flow.tasks.flow_default'

    def get_task_params(self):
        """
        :return: List of (key, params), where key is the user specified key of
                 the task (nvr) and params is a celery task parameters dict.
        """
        return {}

    def fork_import_tasks(self, user_id):
        result = {}
        task_flow = self.get_task_flow()
        for key, task_params in self.get_tasks_params():
            params = copy.deepcopy(task_params)
            params['owner_id'] = user_id
            celery_task = app.send_task(task_flow, [params])
            task = Task.objects.create(
                owner_id=user_id,
                meta_id=celery_task.task_id,
                task_flow=task_flow,
                params=task_params,
            )
            result[key] = {'task_id': task.id}
        return result

    def save(self):
        assert False, "ImportSerializer saving not supported"


class ImportScanOptionsMixin(ImportSerializer):
    """
    Basic options related to package import.
    """
    license_scan = serializers.BooleanField(required=False)
    copyright_scan = serializers.BooleanField(required=False)


class ReleaseImportMixin(ImportSerializer):
    product_release = serializers.CharField(
        allow_null=True,
        required=False,
        max_length=100,
        validators=[release_validator]
    )

    def get_task_params(self):
        params = super(ReleaseImportMixin, self).get_task_params()
        data = self.validated_data
        params['license_scan'] = data.get('license_scan', True)
        params['copyright_scan'] = data.get('copyright_scan', True)

        product_release = data.get('product_release')
        if product_release:
            params['product_release'] = product_release
        return params


class NVRImportSerializer(ImportScanOptionsMixin, ReleaseImportMixin):
    package_nvrs = serializers.ListField(
        child=serializers.CharField()
    )

    def validate(self, attrs):
        attrs = super(NVRImportSerializer, self).validate(attrs)
        return attrs

    def get_tasks_params(self):
        package_nvrs = self.validated_data.get('package_nvrs')
        params = self.get_task_params()
        return [(nvr, dict(package_nvr=nvr, **params)) for nvr in package_nvrs]
