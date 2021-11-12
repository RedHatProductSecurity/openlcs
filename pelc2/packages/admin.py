from django.contrib import admin
from packages.models import File


# Register your models here.
@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = ('id', 'swhid')
    search_fields = ['id', 'swhid']
