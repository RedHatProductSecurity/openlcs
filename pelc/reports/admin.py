from django.contrib import admin

from reports.models import FileLicenseScan
from reports.models import FileCopyrightScan
from reports.models import LicenseDetection
from reports.models import CopyrightDetection


@admin.register(FileLicenseScan)
class FileLicenseScanAdmin(admin.ModelAdmin):
    raw_id_fields = ('file',)
    list_display = ('id', 'file', 'detector')
    search_fields = ['file__swhid', 'detector']


@admin.register(FileCopyrightScan)
class FileCopyrightScanAdmin(admin.ModelAdmin):
    raw_id_fields = ('file',)
    list_display = ('id', 'file', 'detector')
    search_fields = ['file__swhid', 'detector']


@admin.register(LicenseDetection)
class LicenseDetectionAdmin(admin.ModelAdmin):
    raw_id_fields = ('file_scan',)
    list_display = ('id', 'file_scan', 'license_key', 'false_positive')
    search_fields = ['file_scan__file__swhid', 'license_key',
                     'file_scan__detector']


@admin.register(CopyrightDetection)
class CopyrightDetectionAdmin(admin.ModelAdmin):
    raw_id_fields = ('file_scan',)
    list_display = ('id', 'file_scan', 'statement', 'false_positive')
    search_fields = ['file_scan__file__swhid', 'statement',
                     'file_scan__detector']
