from django.contrib import admin

from reports.models import LicenseDetection
from reports.models import CopyrightDetection


@admin.register(LicenseDetection)
class LicenseDetectionAdmin(admin.ModelAdmin):
    raw_id_fields = ('file',)
    list_display = ('file', 'license_key', 'detector', 'false_positive')
    search_fields = ['file__swhid', 'license_key', 'detector']


@admin.register(CopyrightDetection)
class CopyrightDetectionAdmin(admin.ModelAdmin):
    raw_id_fields = ('file',)
    list_display = ('file', 'statement', 'detector', 'false_positive')
    search_fields = ['file__swhid', 'statement', 'detector']
