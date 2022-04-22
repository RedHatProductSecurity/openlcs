from django.contrib import admin

from tasks.models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'meta_id', 'owner', 'params', 'content_object')
    search_fields = ['meta_id', 'owner__username', 'params']
