from rest_framework.viewsets import ModelViewSet
from django_filters import rest_framework as filters

from tasks.models import Task, TaskMeta
from tasks.serializers import TaskSerializer


class TaskFilter(filters.FilterSet):
    status = filters.CharFilter(
        field_name='status', method='filter_status', label='status'
    )
    # input is date format, %Y-%m-%d
    date_done = filters.DateTimeFilter(
        field_name='date_done', method="filter_date_done", label='date_done'
    )
    traceback = filters.CharFilter(
        field_name='traceback', method="filter_traceback", label='traceback'
    )
    params = filters.CharFilter(field_name='params', lookup_expr='contains')

    class Meta:
        model = Task
        fields = ('meta_id', 'params', 'owner__username',
                  'status', 'date_done', 'traceback')

    def filter_status(self, queryset, name, value):
        if not value:
            return queryset

        meta_ids = TaskMeta.objects.filter(
            status=value).values_list('task_id', flat=True)
        return queryset.filter(meta_id__in=meta_ids)

    def filter_date_done(self, queryset, name, value):
        """
        get someday data according input
        """
        if not value:
            return queryset

        meta_ids = TaskMeta.objects.filter(
            date_done__year=value.year,
            date_done__month=value.month,
            date_done__day=value.day).values_list('task_id', flat=True)

        return queryset.filter(meta_id__in=meta_ids)

    def filter_traceback(self, queryset, name, value):
        if not value:
            return queryset

        meta_ids = TaskMeta.objects.filter(
            traceback__icontains=value).values_list('task_id', flat=True)
        return queryset.filter(meta_id__in=meta_ids)


class TaskViewSet(ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    filterset_class = TaskFilter

    def list(self, request, *args, **kwargs):
        """
        Get a list of tasks.

        ####__Request__####

            curl -X GET -H "Content-Type: application/json" \
%(HOST_NAME)s/%(API_PATH)s/tasks/ -H 'Authorization: Token your_token'

        ####__Supported query params__####

        ``meta_id``, string, task meta id.

        ``owner__username``, string, username of the task owner.

        ``status``, string, Status of the task, possible values can be \
``PENDING``, ``STARTED``, ``FAILURE``, ``SUCCESS``, ``RECEIVED``, ``REVOKED``, ``RETRY``.

        ``params``, string, Params of the task, can use part of this field \
to search.

        ``date_done``, string, the day you want to filter the task, format: ``%%Y-%%m-%%d``.

        ``traceback``, string, task traceback, can use part of this field to search


        ####__Response__####

            HTTP 200 OK
            Content-Type: application/json

            [
                {
                    "id": 20,
                    "meta_id": "82b02650-5d36-4430-876a-c8401266b438",
                    "owner": "admin",
                    "params": "{\"package_nvr\": \"fio-3.1-2.el7\", \"license_scan\": true,
                    \"copyright_scan\": true, \"product_release\": \"satellite-6.9.0\"}",
                    "status": "SUCCESS",
                    "date_done": "2022-10-24T09:17:07.406133",
                    "traceback": null
                },
                {
                    "id": 19,
                    "meta_id": "3808b332-45df-4fa2-a4ca-3225549adc2a",
                    "owner": "admin",
                    "params": "{\"package_nvr\": \"ansible-2.4.2.0-2.el7\", \"license_scan\": true,
                     \"copyright_scan\": true, \"product_release\": \"satellite-6.9.0\"}",
                    "status": "STARTED",
                    "date_done": null,
                    "traceback": null
                }
            ]
        """ # noqa
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """
        Get a specific task with task id.

        ``id``: int, task id.

        ``meta_id``: string, task meta id.

        ``owner``: string, task owner.

        ``params``: string, task parameters.

        ``status``: string, task status.

        ``date_done``: string, task done datetime.

        ``traceback``: string, task traceback.

        ####__Request__####

            curl -X GET -H "Content-Type: application/json" -H \
'Authorization: Token your_token' %(HOST_NAME)s/%(API_PATH)s/tasks/instance_pk/

        ####__Response__####

            HTTP 200 OK
            Content-Type: application/json

            {
                "id": 20,
                "meta_id": "82b02650-5d36-4430-876a-c8401266b438",
                "owner": "admin",
                "params": "{\"package_nvr\": \"fio-3.1-2.el7\", \"license_scan\": true,
                \"copyright_scan\": true, \"product_release\": \"satellite-6.9.0\"}",
                "status": "SUCCESS",
                "date_done": "2022-10-24T09:17:07.406133",
                "traceback": null
            }
        """ # noqa
        return super().retrieve(request, *args, **kwargs)
