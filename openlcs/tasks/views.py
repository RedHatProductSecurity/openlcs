from celery.states import SUCCESS, STARTED, FAILURE,\
    RECEIVED, REVOKED, RETRY, PENDING
from rest_framework.viewsets import ModelViewSet
from django_filters import rest_framework as filters

from tasks.models import Task, TaskMeta
from tasks.serializers import TaskSerializer

# task status list for DRF’s browsable API
TASK_STATUS_CHOICES = (
    (PENDING, PENDING),
    (STARTED, STARTED),
    (FAILURE, FAILURE),
    (SUCCESS, SUCCESS),
    (RECEIVED, RECEIVED),
    (REVOKED, REVOKED),
    (RETRY, RETRY)
)


class TaskFilter(filters.FilterSet):
    status = filters.ChoiceFilter(
        field_name='status', method='filter_status', label='status',
        choices=TASK_STATUS_CHOICES
    )
    # input is date format, %Y-%m-%d
    date_done = filters.DateTimeFilter(
        field_name='date_done', method="filter_date_done", label='date_done'
    )
    traceback = filters.CharFilter(
        field_name='traceback', method="filter_traceback", label='traceback'
    )
    params = filters.CharFilter(
        field_name='params', lookup_expr='contains', label='params'
    )
    owner__username = filters.CharFilter(
        field_name='owner__username', label='owner__username'
    )
    meta_id = filters.CharFilter(field_name='meta_id', label='meta_id')

    class Meta:
        model = Task
        fields = ('meta_id', 'owner__username', 'status',
                  'params', 'date_done', 'traceback')

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

        with query params
        
            curl -X GET -H "Content-Type: application/json" \
%(HOST_NAME)s/%(API_PATH)s/tasks/?meta_id=&owner__username=&status=&params=&date_done=&traceback= \
 -H 'Authorization: Token your_token'        


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
                    "id": 5,
                    "meta_id": "60747ba3-653f-4669-b37e-08eb8b3ae14f",
                    "owner": "admin",
                    "params": "{\"package_nvr\": \"ansible-2.4.2.0-2.el7\", \"license_scan\": true,
                     \"copyright_scan\": true, \"product_release\": \"satellite-6.9.0\"}",
                    "status": "SUCCESS",
                    "date_done": "2022-11-10T05:39:45.746881",
                    "traceback": null,
                    "object_url": "%(HOST_NAME)s/rest/v1/sources/2/"
                },
                {
                    "id": 6,
                    "meta_id": "ddc8d40a-3c85-4a14-ace8-440c7e69ad55",
                    "owner": "admin",
                    "params": "{\"package_nvr\": \"fio-3.1-2.el7\", \"license_scan\": true,
                     \"copyright_scan\": true, \"product_release\": \"satellite-6.9.0\"}",
                    "status": "SUCCESS",
                    "date_done": "2022-11-10T05:38:50.461372",
                    "traceback": null,
                    "object_url": "%(HOST_NAME)s/rest/v1/sources/1/"
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
        
        ``object_url``: string, source object url.

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
                "traceback": null,
                "object_url": "%(HOST_NAME)s/rest/v1/sources/1/"
            }
        """ # noqa
        return super().retrieve(request, *args, **kwargs)
