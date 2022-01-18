from rest_framework.filters import SearchFilter
from rest_framework.viewsets import ModelViewSet

from tasks.models import Task
from tasks.serializers import TaskSerializer


class TaskViewSet(ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    filter_backends = [SearchFilter]
    search_fields = ['=meta_id', '=owner__username', '$params']

    def list(self, request, *args, **kwargs):
        """
        Get a list of tasks.

        ####__Request__####

            curl -X GET -H "Content-Type: application/json" \
%(HOST_NAME)s/%(API_PATH)s/tasks/ -H 'Authorization: Token your_token'

        ####__Response__####

            HTTP 200 OK
            Content-Type: application/json

            [
                {
                    "id": 1,
                    "meta_id": "1e234842-0993-4e3a-8bb7-7dd9bed6f28c",
                    "owner": "qduanmu",
                    "params": "{\"package_nvr\": \"a2ps-4.14-23.el7\", \
\"license_scan\": true, \"copyright_scan\": true}"
                },
                {
                    "id": 2,
                    "meta_id": "c0e0fff0-1ab6-4f2b-851c-eaf969988df3",
                    "owner": "qduanmu",
                    "params": "{\"package_nvr\": \"ansible-2.4.2.0-2.el7\", \
\"license_scan\": false, \"copyright_scan\": true, \"product_release\": \
\"satellite-6.9.0\"}"
                },
            ]
        """
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """
        Get a specific task with task id.

        ``id``: int, task id.

        ``meta_id``: string, task meta id.

        ``owner``: string, task owner.

        ``params``: string, task parameters.

        ####__Request__####

            curl -X GET -H "Content-Type: application/json" -H \
'Authorization: Token your_token' %(HOST_NAME)s/%(API_PATH)s/tasks/instance_pk/

        ####__Response__####

            HTTP 200 OK
            Content-Type: application/json

            {
                "id": 1,
                "meta_id": "1e234842-0993-4e3a-8bb7-7dd9bed6f28c",
                "owner": "qduanmu",
                "params": "{\"package_nvr\": \"a2ps-4.14-23.el7\", \
\"license_scan\": true, \"copyright_scan\": true}"
            }
        """
        return super().retrieve(request, *args, **kwargs)
