from rest_framework import status
from rest_framework.parsers import FileUploadParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.pagination import LimitOffsetPagination
from rest_framework_extensions.cache.decorators import cache_response
from rest_framework_extensions.key_constructor.bits import (
    ListSqlQueryKeyBit,
    PaginationKeyBit,
    RetrieveSqlQueryKeyBit
)
from rest_framework_extensions.key_constructor.constructors import (
    DefaultKeyConstructor
)
from datetime import datetime
from django.core.cache import cache
from rest_framework_extensions.key_constructor.bits import KeyBitBase

from libs.parsers import parse_manifest_file
from products.models import Release
from products.serializers import ReleaseSerializer
from django.conf import settings
import logging
logger = logging.getLogger(__name__)


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


class ReleaseLimitOffsetPagination(LimitOffsetPagination):
    default_limit = 5
    limit_query_param = 'limit'
    offset_query_param = 'offset'
    max_limit = 10


class ReleaseUpdatedAtKeyBit(KeyBitBase):
    """
    http://chibisov.github.io/drf-extensions/docs/#key-constructors
    The key: release_updated_at will be updated in redis when the model
    `Release` saved or deleted, so we get it from cache firstly;
    If the key does not exist, we prefer to set a new one in cache.
    """
    key = "release_updated_at"

    def get_data(self, **kwargs):
        value = cache.get(self.key, None)
        if not value:
            value = datetime.utcnow()
            cache.set(self.key, value=value)
        logger.info("ReleaseUpdatedAt: %s (UTC time)", value)
        return str(value)


class ReleaseListKeyConstructor(DefaultKeyConstructor):
    list_sql = ListSqlQueryKeyBit()
    pagination = PaginationKeyBit()
    updated_at = ReleaseUpdatedAtKeyBit()


class ReleaseObjectKeyConstructor(DefaultKeyConstructor):
    retrieve_sql = RetrieveSqlQueryKeyBit()
    updated_at = ReleaseUpdatedAtKeyBit()


class ReleaseViewSet(ModelViewSet):
    """
    API endpoint that allows releases to be viewed.
    """
    queryset = Release.objects.all()
    serializer_class = ReleaseSerializer
    pagination_class = ReleaseLimitOffsetPagination

    @cache_response(timeout=settings.RELEASE_LIST_CACHE_TIMEOUT,
                    key_func=ReleaseListKeyConstructor())
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
                    "product": {
                        "id": 1,
                        "name": "product",
                        "display_name": "",
                        "description": "",
                        "family": ""
                    },
                    "components": [],
                    "version": "6.9.0",
                    "name": "satellite-6.9.0",
                    "notes": "The most authoritative list comes from Errata.."
                }
            ]
        """
        return super().list(request, *args, **kwargs)

    @cache_response(timeout=settings.RELEASE_RETRIEVE_CACHE_TIMEOUT,
                    key_func=ReleaseObjectKeyConstructor())
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
                "product": {
                    "id": 1,
                    "name": "product",
                    "display_name": "",
                    "description": "",
                    "family": ""
                },
                "components": [],
                "version": "6.9.0",
                "name": "satellite-6.9.0",
                "notes": "The most authoritative list comes from Errata.."
            }
        """
        return super().retrieve(request, *args, **kwargs)
