from django.contrib import admin
from packages.models import File
from packages.models import Path
from packages.models import Source
from packages.models import Package


# Register your models here.
@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = ('id', 'swhid')
    search_fields = ['id', 'swhid']


@admin.register(Path)
class PathAdmin(admin.ModelAdmin):
    raw_id_fields = ('source', 'file')
    list_display = ('source', 'file', 'path')
    search_fields = ['source__name', 'file__swhid', 'path']


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ('checksum', 'name', 'url', 'state', 'archive_type')
    search_fields = ['checksum', 'name', 'url', 'archive_type']


@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    raw_id_fields = ('source',)
    list_display = ('nvr', 'source', 'sum_license', 'is_source')
    search_fields = ['nvr', 'source__name', 'sum_license']
