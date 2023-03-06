from rest_framework.viewsets import ModelViewSet

from reports.models import LicenseDetection
from reports.models import CopyrightDetection
from reports.serializers import LicenseDetectionSerializer
from reports.serializers import CopyrightDetectionSerializer
import django_filters


class LicenseDetectionFilter(django_filters.FilterSet):
    """Class that filters queries to LicenseDetection list views."""
    ld_id = django_filters.CharFilter(field_name='id', method='filter_id')
    license_key = django_filters.CharFilter(
            field_name='license_key', lookup_expr='iexact')

    def filter_id(self, queryset, *args):
        id_list = []
        if args[0] == 'id':
            id_list = [int(num.strip())
                       for num in args[1].split(',')]
        return queryset.filter(id__in=id_list)

    class Meta:
        model = LicenseDetection
        fields = ('ld_id', 'license_key',)


class LicenseDetectionViewSet(ModelViewSet):
    """
    API endpoint that allows license detected to be viewed.
    """
    queryset = LicenseDetection.objects.all()
    serializer_class = LicenseDetectionSerializer
    filter_class = LicenseDetectionFilter

    def get_serializer_context(self):
        content = super().get_serializer_context()
        content['source_id'] = self.request.GET.get('source_id')
        return content

    def list(self, request, *args, **kwargs):
        """
        Get a list of license detections.

        ####__Request__####

            curl -X GET -H "Content-Type: application/json" \
-H 'Authorization: Token your_token' \
%(HOST_NAME)s/%(API_PATH)s/licensedetections/

        ####__Response__####

            HTTP 200 OK
            Content-Type: application/json

            [
                {
                    "id": 72,
                    "license_key": "gpl-2.0",
                    "score": 100.0,
                    "rule": "gpl-2.0_34.RULE",
                    "start_line": 6,
                    "end_line": 17,
                    "false_positive": false,
                    "file_data": {}
                },
                {
                    "id": 73,
                    "license_key": "bsd-simplified",
                    "score": 100.0,
                    "rule": "bsd-simplified_97.RULE",
                    "start_line": 4,
                    "end_line": 4,
                    "false_positive": false,
                    "file_data": {}
                }
            ]
        """
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """
        Get a specific license detection.

        ####__Request__####

            curl -X GET -H "Content-Type: application/json" \
-H 'Authorization: Token your_token' \
%(HOST_NAME)s/%(API_PATH)s/licensedetections/instance_pk/

        ####__Response__####

            HTTP 200 OK
            Content-Type: application/json

            {
                "id": 72,
                "license_key": "gpl-2.0",
                "score": 100.0,
                "rule": "gpl-2.0_34.RULE",
                "start_line": 6,
                "end_line": 17,
                "false_positive": false,
                "file_data": {}
            }
        """
        return super().retrieve(request, *args, **kwargs)


class CopyrightDetectionFilter(django_filters.FilterSet):
    """Class that filters queries to CopyrightDetection list views."""
    ld_id = django_filters.CharFilter(field_name='id', method='filter_id')
    statement = django_filters.CharFilter(
            field_name='statement', lookup_expr='iexact')

    def filter_id(self, queryset, *args):
        id_list = []
        if args[0] == 'id':
            id_list = [int(num.strip())
                       for num in args[1].split(',')]
        return queryset.filter(id__in=id_list)

    class Meta:
        model = CopyrightDetection
        fields = ('ld_id', 'statement',)


class CopyrightDetectionViewSet(ModelViewSet):
    """
    API endpoint that allows copyright detected to be viewed.
    """
    queryset = CopyrightDetection.objects.all()
    serializer_class = CopyrightDetectionSerializer
    filter_class = CopyrightDetectionFilter

    def get_serializer_context(self):
        content = super().get_serializer_context()
        content['source_id'] = self.request.GET.get('source_id')
        return content

    def list(self, request, *args, **kwargs):
        """
        Get a list of copyright detections.

        ####__Request__####

            curl -X GET -H "Content-Type: application/json" \
-H 'Authorization: Token your_token' \
%(HOST_NAME)s/%(API_PATH)s/copyrightdetections/

        ####__Response__####

            HTTP 200 OK
            Content-Type: application/json

            [
                {
                    "id": 1,
                    "statement": \
"Copyright (c) 2005 Jens Axboe <axboe@suse.de>",
                    "false_positive": false,
                    "start_line": 4,
                    "end_line": 4,
                    "file_data": {}
                },
                {
                    "id": 2,
                    "statement": \
"Copyright (c) 2006-2012 Jens Axboe <axboe@kernel.dk>",
                    "false_positive": false,
                    "start_line": 5,
                    "end_line": 5,
                    "file_data": {}
                }
            ]
        """
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """
        Get a specific copyright detection.

        ####__Request__####

            curl -X GET -H "Content-Type: application/json" \
-H 'Authorization: Token your_token' \
%(HOST_NAME)s/%(API_PATH)s/licensedetections/instance_pk/

        ####__Response__####

            HTTP 200 OK
            Content-Type: application/json

            {
                "id": 1,
                "statement": "Copyright (c) 2005 Jens Axboe <axboe@suse.de>",
                "false_positive": false,
                "start_line": 4,
                "end_line": 4,
                "file_data": {}
            }
        """
        return super().retrieve(request, *args, **kwargs)
