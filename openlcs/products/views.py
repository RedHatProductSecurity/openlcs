from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import FileUploadParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from libs.parsers import parse_manifest_file
from products.models import Release
from products.serializers import ReleaseSerializer
from products.serializers import ReleasePackageSerializer


class ManifestFileParserView(APIView):

    parser_classes = [FileUploadParser]

    def put(self, request, format=None):
        """
        The API endpoint is used to upload/parse manifest file.

        ####__Request__####

            curl -X PUT -H "Authorization: Token your_token" \
-H 'Content-Disposition: attachment; filename=data.json' \
-d @data.json %(HOST_NAME)s/%(API_PATH)s/manifest_parser/

        ####__Response__####
            Success: HTTP 200 with json data with below format:
            {
                "productname": "satellite",
                "version": "6.9.0",
                "notes": "Notes goes here",
                "containers": [],
                "src_packages": ["ansible-2.4.2.0-2.el7",
                                 "ansiblerole-foreman_scap_client-0.1.0-1.el7sat",
                                 ...
                                ]
            }

            Error: HTTP 400 BAD REQUEST
        """
        manifest_file = request.data['file']
        try:
            data = parse_manifest_file(manifest_file)
        except RuntimeError as e:
            return Response(
                f"Runtime error: {e.args[0]}",
                status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(data=data, status=status.HTTP_200_OK)


class ReleaseViewSet(ModelViewSet):
    """
    API endpoint that allows releases to be viewed.
    """
    queryset = Release.objects.all()
    serializer_class = ReleaseSerializer

    def get_serializer_class(self):
        if self.action in ["report"]:
            return ReleasePackageSerializer
        return super().get_serializer_class()

    def list(self, request, *args, **kwargs):
        """
        Get a list of product releases.

        ####__Request__####

            curl -X GET -H "Content-Type: application/json" \
-H 'Authorization: Token your_token' %(HOST_NAME)s/%(API_PATH)s/releases/

        ####__Response__####

            HTTP 200 OK
            Content-Type: application/json

            [
                {
                    "id": 1,
                    "version": "6.9.0",
                    "name": "satellite-6.9.0",
                    "notes": "The most authoritative list comes from Errata..",
                    "product": 1
                }
            ]
        """
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """
        Get a specific product release.

        ####__Request__####

            curl -X GET -H "Content-Type: application/json" \
-H 'Authorization: Token your_token' \
%(HOST_NAME)s/%(API_PATH)s/releases/instance_pk/

        ####__Response__####

            HTTP 200 OK
            Content-Type: application/json

            {
                "id": 1,
                "version": "6.9.0",
                "name": "satellite-6.9.0",
                "notes": "The most authoritative list comes from Errata..",
                "product": 1
            }
        """
        return super().retrieve(request, *args, **kwargs)

    @action(detail=True)
    def report(self, request, pk):
        """
        Get a specific product release report data.

        ####__Request__####

            curl -X GET -H "Content-Type: application/json" \
-H 'Authorization: Token your_token' \
%(HOST_NAME)s/%(API_PATH)s/releases/instance_pk/report/

        ####__Response__####

            HTTP 200 OK
            Content-Type: application/json

            [
                {
                    "scan_result": {},
                    "package_nvr": "python-ecdsa-0.11-4.el7",
                    "is_source": true
                },
                {
                    "scan_result": {
                        "sum_license": "GPLv2",
                        "url": "http://git.kernel.dk/?p=fio.git;a=summary",
                        "licenses": [
                            "public-domain",
                            "bsd-simplified",
                            "gpl-2.0-plus",
                            "gpl-2.0",
                            "gpl-1.0-plus"
                        ],
                        "copyrights": []
                    },
                    "package_nvr": "fio-3.1-2.el7",
                    "is_source": true
                },
                ...
            ]
        """

        release = self.get_object()
        packages = release.packages.all()
        serializer = self.get_serializer(packages, many=True)
        return Response(data=serializer.data, status=status.HTTP_200_OK)
