from django.contrib import admin

from tasks.models import Task, TaskMeta


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'meta_id', 'owner', 'params',
                    'content_object', 'parent_task_id')
    search_fields = ['meta_id', 'owner__username', 'params', 'parent_task_id']


@admin.register(TaskMeta)
class TaskMetaAdmin(admin.ModelAdmin):
    list_display = ('pk', 'task_id', 'status', 'date_done')
    search_fields = ['id', 'task_id', 'status']
