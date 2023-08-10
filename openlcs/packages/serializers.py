import copy
import os
import sys
from libs.swh_tools import swhid_check
from libs.celery_helper import generate_priority_kwargs, ALLOW_PRIORITY
from packages.models import (
    Component,
    File,
    Path,
    Source,
    ComponentSubscription,
)
from products.models import Release
from rest_framework import serializers
from tasks.models import Task
from django_celery_beat.models import (
    PeriodicTask,
    CrontabSchedule,
)
from django.conf import settings
from django.utils.http import urlquote

# pylint:disable=no-name-in-module,import-error
from openlcs.celery import app

# Fix absolute import issue in openlcs.
openlcs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if openlcs_dir not in sys.path:
    sys.path.append(openlcs_dir)
from libs.common import get_component_name_version_combination  # noqa: E402


class AbstractSerializerMixin(serializers.Serializer):
    def create(self, validated_data):
        pass

    def update(self, instance, validated_data):
        pass


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


class BulkFileSerializer(AbstractSerializerMixin):
    """
    Bulk file serializer, use to return validate files after created.
    """

    files = FileSerializer(many=True)


class SourceSerializer(serializers.ModelSerializer):
    """
    Source serializer.
    """
    license_detections = serializers.SerializerMethodField()
    copyright_detections = serializers.SerializerMethodField()

    class Meta:
        model = Source
        fields = ["id", "name", "url", "checksum", "state", "archive_type",
                  "scan_flag", "component_set", "license_detections",
                  "copyright_detections"]

    def get_license_detections(self, obj):
        license_data = obj.get_license_detections().values_list(
            'license_key', flat=True)
        ld_url_prefix = 'http://{}/rest/v1/licensedetections/'.format(
                        settings.HOSTNAME)
        source_id = obj.id
        license_detections = dict()
        for lk in license_data.distinct():
            detail_url = '{}?source_id={}&license_key={}'.format(
                        ld_url_prefix, source_id, urlquote(lk))
            license_detections[lk] = detail_url
        return license_detections

    def get_copyright_detections(self, obj):
        copyrights = obj.get_copyright_detections().values_list(
            'statement', flat=True)
        cr_url_prefix = 'http://{}/rest/v1/copyrightdetections/'.format(
                        settings.HOSTNAME)
        source_id = obj.id
        copyright_detections = dict()
        for stm in copyrights.distinct():
            detail_url = '{}?source_id={}&statement={}'.format(
                        cr_url_prefix, source_id, urlquote(stm))
            copyright_detections[stm] = detail_url
        return copyright_detections


class PathSerializer(serializers.ModelSerializer):
    """
    Path serializer
    """

    source = serializers.SlugRelatedField(
        queryset=Source.objects.all(),
        slug_field='checksum',
        allow_null=False,
        required=True,
    )
    file = serializers.SlugRelatedField(
        queryset=File.objects.all(),
        slug_field='swhid',
        allow_null=False,
        required=True,
    )

    class Meta:
        model = Path
        fields = "__all__"


class BulkPathSerializer(AbstractSerializerMixin):
    """
    Bulk file serializer, use to return validate paths after created.
    """

    paths = PathSerializer(many=True)


class CreatePathSerializer(AbstractSerializerMixin):
    """
    Create path serializer, use to return validated paths data in paths list.
    """

    file = serializers.SlugRelatedField(
        queryset=File.objects.all(),
        slug_field='swhid',
        allow_null=False,
        required=True,
    )
    path = serializers.CharField(required=True)


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


class ImportSerializer(AbstractSerializerMixin):
    def get_task_flow(self):
        return 'flow.tasks.flow_default'

    def get_task_params(self):
        """
        :return: List of (key, params), where key is the user specified key of
                 the task (nvr) and params is a celery task parameters dict.
        """
        return {}

    def fork_import_tasks(self, user_id, parent_task_id, token):
        result = {}
        task_flow = self.get_task_flow()
        for key, task_params in self.get_tasks_params():
            params = copy.deepcopy(task_params)
            params['owner_id'] = user_id
            params['token'] = token
            params['parent_task_id'] = parent_task_id
            celery_task = app.send_task(
                task_flow,
                [params],
                **generate_priority_kwargs(params['priority'])
            )
            task = Task.objects.create(
                owner_id=user_id,
                meta_id=celery_task.task_id,
                task_flow=task_flow,
                params=task_params,
                parent_task_id=parent_task_id
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
    priority = serializers.CharField(required=False)
    subscription_id = serializers.IntegerField(required=False)
    parent_component = serializers.JSONField(required=False)

    def validate_priority(self, value):
        if value not in ALLOW_PRIORITY:
            raise serializers.ValidationError(
                f"priority must be one of {ALLOW_PRIORITY}"
            )
        return value


class ReleaseImportMixin(ImportSerializer):
    src_dir = serializers.CharField(required=False)
    parent = serializers.CharField(required=False)
    component_type = serializers.CharField(required=False)
    product_release = serializers.CharField(
        allow_null=True,
        required=False,
        max_length=100,
        validators=[release_validator],
    )

    def get_task_params(self):
        params = super(ReleaseImportMixin, self).get_task_params()
        data = self.validated_data
        params['license_scan'] = data.get('license_scan', True)
        params['copyright_scan'] = data.get('copyright_scan', True)
        params['priority'] = data.get('priority', 'low')
        src_dir = data.get('src_dir', None)
        component_type = data.get('component_type', None)
        product_release = data.get('product_release')
        parent = data.get('parent', None)
        component = data.get('component', None)
        provenance = data.get('provenance')
        subscription_id = data.get("subscription_id")
        parent_component = data.get("parent_component")

        if src_dir is not None:
            params['src_dir'] = src_dir
        if component_type is not None:
            params['component_type'] = component_type
        if parent is not None:
            params['parent'] = parent
        if product_release:
            params['product_release'] = product_release
        if component:
            params['component'] = component
        if provenance:
            params['provenance'] = provenance
        if subscription_id is not None:
            params['subscription_id'] = subscription_id
        if parent_component:
            params['parent_component'] = parent_component

        return params


class NVRImportSerializer(ImportScanOptionsMixin, ReleaseImportMixin):
    package_nvrs = serializers.ListField(child=serializers.CharField())

    def validate(self, attrs):
        attrs = super(NVRImportSerializer, self).validate(attrs)
        return attrs

    def get_tasks_params(self):
        package_nvrs = self.validated_data.get('package_nvrs')
        params = self.get_task_params()
        return [(nvr, dict(package_nvr=nvr, **params)) for nvr in package_nvrs]


class RSImportSerializer(ImportScanOptionsMixin, ReleaseImportMixin):
    rs_comps = serializers.ListField(child=serializers.DictField())

    def get_tasks_params(self):
        params = self.get_task_params()
        result = []
        rs_comps = self.validated_data.get('rs_comps')
        for rs_comp in rs_comps:
            result.append(
                (get_component_name_version_combination(rs_comp),
                 dict(rs_comp=rs_comp, **params))
            )
        return result


class ComponentImportSerializer(ImportScanOptionsMixin, ReleaseImportMixin):
    components = serializers.ListField(child=serializers.DictField())
    provenance = serializers.CharField(required=True)

    def validate(self, attrs):
        attrs = super(ComponentImportSerializer, self).validate(attrs)
        return attrs

    def get_tasks_params(self):
        params = self.get_task_params()
        components = self.validated_data.get('components')
        need_keys = (
            "uuid", "link", "type", "name", "version", "release", "nvr",
            "arch", "nevra", "software_build", "download_url"
        )
        comp_params = []
        for component in components:
            subcomp = {k: component[k] for k in component.keys() & need_keys}
            updated_params = (
                component.get('nvr'), dict(component=subcomp, **params))
            comp_params.append(updated_params)
        return comp_params


class ComponentSerializer(serializers.ModelSerializer):
    source = SourceSerializer(required=False)
    provides = serializers.SerializerMethodField()

    class Meta:
        model = Component
        fields = '__all__'

    def get_provides(self, obj):
        provides = []
        if obj.type in ['OCI', 'RPMMOD']:
            node = obj.component_nodes.get()
            descendant_nodes = node.get_descendants()
            descendant_components = Component.objects.filter(
                id__in=descendant_nodes.values_list('object_id', flat=True)
            )
            serializer = ComponentSerializer(descendant_components, many=True)
            provides = serializer.data
        return provides


class ComponentSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComponentSubscription
        fields = "__all__"


class PeriodicTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = PeriodicTask
        fields = ['id', 'name', 'task', 'one_off', 'last_run_at',
                  'date_changed', 'crontab', 'priority', 'enabled']


class CrontabScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = CrontabSchedule
        fields = ['id', 'minute', 'hour', 'day_of_week', 'day_of_month',
                  'month_of_year']
