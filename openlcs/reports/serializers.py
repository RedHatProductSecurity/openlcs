from rest_framework import serializers

from reports.models import LicenseDetection
from reports.models import CopyrightDetection
from reports.models import FileLicenseScan, FileCopyrightScan
from packages.views import Path


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
