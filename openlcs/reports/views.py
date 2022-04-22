from rest_framework.viewsets import ModelViewSet

from reports.models import LicenseDetection
from reports.models import CopyrightDetection
from reports.serializers import LicenseDetectionSerializer
from reports.serializers import CopyrightDetectionSerializer


class LicenseDetectionViewSet(ModelViewSet):
    """
    API endpoint that allows license detected to be viewed.
    """
    queryset = LicenseDetection.objects.all()
    serializer_class = LicenseDetectionSerializer

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
                    "file_scan": 1
                },
                {
                    "id": 73,
                    "license_key": "bsd-simplified",
                    "score": 100.0,
                    "rule": "bsd-simplified_97.RULE",
                    "start_line": 4,
                    "end_line": 4,
                    "false_positive": false,
                    "file_scan": 2
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
                "file_scan": 1
            }
        """
        return super().retrieve(request, *args, **kwargs)


class CopyrightDetectionViewSet(ModelViewSet):
    """
    API endpoint that allows copyright detected to be viewed.
    """
    queryset = CopyrightDetection.objects.all()
    serializer_class = CopyrightDetectionSerializer

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
                    "file_scan": 1
                },
                {
                    "id": 2,
                    "statement": \
"Copyright (c) 2006-2012 Jens Axboe <axboe@kernel.dk>",
                    "false_positive": false,
                    "start_line": 5,
                    "end_line": 5,
                    "file_scan": 2
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
                "file_scan": 1
            }
        """
        return super().retrieve(request, *args, **kwargs)
