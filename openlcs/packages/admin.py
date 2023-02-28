from django.contrib import admin
from django import forms

from packages.models import File
from packages.models import Path
from packages.models import Source
from packages.models import Component, ComponentSubscription


# Register your models here.
@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = ('id', 'swhid')
    search_fields = ['id', 'swhid']


@admin.register(Path)
class PathAdmin(admin.ModelAdmin):
    raw_id_fields = ('source', 'file')
    list_display = ('id', 'source', 'file', 'path')
    search_fields = ['source__name', 'file__swhid', 'path']


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ('id', 'checksum', 'name', 'url', 'state', 'archive_type')
    search_fields = ['checksum', 'name', 'url', 'archive_type']


@admin.register(Component)
class ComponentAdmin(admin.ModelAdmin):
    search_fields = ['uuid', 'purl', 'type', 'name']
    list_display = ('name', 'version', 'release', 'arch', 'type',
                    'from_corgi', 'sync_status', 'sync_failure_reason')


def activate_selected(modeladmin, request, queryset):
    queryset.update(active=True)
    message = "Successfully activated selected component subscriptions"
    modeladmin.message_user(request, message)


def deactivate_selected(modeladmin, request, queryset):
    queryset.update(active=False)
    message = "Successfully deactivated selected component subscriptions"
    modeladmin.message_user(request, message)


activate_selected.short_description = "Activate selected subscriptions"
deactivate_selected.short_description = "Deactivate selected subscriptions"


@admin.register(ComponentSubscription)
class ComponentSubscriptionAdmin(admin.ModelAdmin):
    search_fields = ['name', 'query_params__icontains']
    list_display = ('name', 'query_params', 'created_at', 'updated_at',
                    'active',)
    list_filter = ('active',)
    actions = [activate_selected, deactivate_selected]

    def get_form(self, request, obj=None, **kwargs):
        kwargs['widgets'] = {
            'component_purls': forms.Textarea(attrs={'rols': 100, 'cols': 100})
        }
        return super().get_form(request, obj, **kwargs)
