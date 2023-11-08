from rest_framework import serializers

from reports.models import LicenseDetection
from reports.models import CopyrightDetection
from reports.models import FileLicenseScan, FileCopyrightScan
from packages.models import Path
from packages.models import ComponentSubscription
from tasks.models import Task

from celery.states import SUCCESS, FAILURE


class LicenseDetectionSerializer(serializers.ModelSerializer):
    """
    LicenseDetection serializer.
    """
    file_data = serializers.SerializerMethodField()

    class Meta:
        model = LicenseDetection
        fields = ('id', 'license_key', 'score', 'rule', 'start_line',
                  'end_line', 'false_positive', 'file_data',)

    def get_file_data(self, obj):
        file_data = dict()
        try:
            file_licensescan = FileLicenseScan.objects.get(id=obj.file_scan_id)
        except FileLicenseScan.DoesNotExist:
            return None
        file_id = file_licensescan.file_id
        swhid = file_licensescan.file.swhid
        detector = file_licensescan.detector
        source_id = self.context.get('source_id')
        file_path = ''
        if source_id is not None:
            try:
                package_path = Path.objects.filter(
                    file_id=file_id, source_id=source_id)
                path = package_path.values_list('path', flat=True)
                if path and len(path) >= 1:
                    file_path = path[0]
            except Path.DoesNotExist:
                file_path = ''

        file_scan = {
            'file_id': file_id,
            'swhid': swhid,
            'detector': detector
        }
        file_data = {
            'file_path': file_path,
            'file_scan': file_scan
        }
        return file_data


class CopyrightDetectionSerializer(serializers.ModelSerializer):
    """
    CopyrightDetection serializer.
    """
    file_data = serializers.SerializerMethodField()

    class Meta:
        model = CopyrightDetection
        fields = ('id', 'statement', 'false_positive',
                  'start_line', 'end_line', 'file_data',)

    def get_file_data(self, obj):
        try:
            file_copyrightscan = FileCopyrightScan.objects.get(
                id=obj.file_scan_id)
        except FileCopyrightScan.DoesNotExist:
            return None
        file_id = file_copyrightscan.file_id
        swhid = file_copyrightscan.file.swhid
        detector = file_copyrightscan.detector
        source_id = self.context.get('source_id')
        file_path = ''
        if source_id is not None:
            try:
                package_path = Path.objects.filter(
                    file_id=file_id, source_id=source_id)
                path = package_path.values_list('path', flat=True)
                if path and len(path) >= 1:
                    file_path = path[0]
            except Path.DoesNotExist:
                file_path = ''
        file_scan = {
            'file_id': file_id,
            'swhid': swhid,
            'detector': detector
        }
        file_data = {
            'file_path': file_path,
            'file_scan': file_scan
        }
        return file_data


class ReportMetricsSerializer(serializers.ModelSerializer):
    """
    Report metrics serializer.
    """

    total_scans = serializers.SerializerMethodField()
    success_scans = serializers.SerializerMethodField()
    complete_scans = serializers.SerializerMethodField()

    class Meta:
        model = ComponentSubscription
        fields = ["name", "active", "query_params", "total_scans",
                  "success_scans", "complete_scans"]

    def get_total_scans(self, obj):
        return len(obj.source_purls) if obj.source_purls else 0

    def get_success_scans(self, obj):
        purls = []
        components = obj.get_synced_components()
        purls = [component.purl for component in components]
        return len(purls)

    def get_complete_scans(self, obj):
        subscription_id = obj.id
        task_objs = Task.objects.filter(
            params__contains=f'subscription_id\": {subscription_id}'
        )
        count = 0
        complete_state = ["DUPLICATE", SUCCESS, FAILURE]
        for task_obj in task_objs:
            if task_obj.status in complete_state:
                count += 1

        return count
