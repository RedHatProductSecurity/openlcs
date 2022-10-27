import json
import time

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from libs.parsers import parse_manifest_file
from packages.mixins import (
    PackageImportTransactionMixin,
    SaveScanResultMixin,
    SaveComponentsMixin
)
from packages.models import Component, File, Path, Source
from packages.serializers import (
    BulkCreateFileSerializer,
    BulkCreatePathSerializer,
    ComponentSerializer,
    FileSerializer,
    NVRImportSerializer,
    PathSerializer,
    RSImportSerializer,
    SourceSerializer
)
from products.models import Product, Release
from reports.models import FileCopyrightScan, FileLicenseScan
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import FileUploadParser, JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet


# Create your views here.
class FileViewSet(ModelViewSet, PackageImportTransactionMixin):
    """
    API endpoint that allows files to be viewed or edited.
    """
    queryset = File.objects.all()
    serializer_class = FileSerializer
    bulk_create_file_serializer = BulkCreateFileSerializer

    def list(self, request, *args, **kwargs):
        """
        Get a list of files.

        ####__Request__####

            curl -X GET -H "Content-Type: application/json" \
%(HOST_NAME)s/%(API_PATH)s/files/  -H 'Authorization: Token your_token'

        ####__Response__####

            HTTP 200 OK
            Content-Type: application/json
            [
                {
                    "id": 1,
                    "swhid": \
"swh:1:cnt:1fa0d32c021a24447540ab6dca496948de8088aa"
                },
                {
                    "id": 2,
                    "swhid": \
"swh:1:cnt:1fa0d32c021a24447540ab6dca496948de8088ab"
                },
                {
                    "id": 3,
                    "swhid": \
"swh:1:cnt:1fa0d32c021a24447540ab6dca496948de8088ac"
                },
                {
                    "id": 4,
                    "swhid": \
"swh:1:cnt:1fa0d32c021a24447540ab6dca496948de8088ad"
                }
            ]

        """
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """
        Create a new file.

        ####__Request__####

            curl -X POST -H "Content-Type: application/json" \
%(HOST_NAME)s/%(API_PATH)s/files/ \
-d '{"swhid": "swh:1:cnt:1fa0d32c021a24447540ab6dca496948de8088cc"}' \
-H 'Authorization: Token your_token'

        ####__Response__####

            {
                "id": 5,
                "swhid": "swh:1:cnt:1fa0d32c021a24447540ab6dca496948de8088cc"
            }

            or

            {
                "swhid": ["file with this SWH ID already exists."]
            }
        """
        return super().create(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """
        Get a specific file.

        ####__Request__####

            curl -X GET -H "Content-Type: application/json" \
%(HOST_NAME)s/%(API_PATH)s/files/instance_pk/ -H 'Authorization: \
Token your_token'

        ####__Response__####

            HTTP 200 OK
            Content-Type: application/json
            {
                "id": 1,
                "swhid": "swh:1:cnt:1fa0d32c021a24447540ab6dca496948de8088ac"
            }
        """
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """
        Update file from command line.

        ####__Request__####

            curl -X PATCH -H "Content-Type: application/json" \
%(HOST_NAME)s/%(API_PATH)s/files/instance_pk/ -d \
'{"swhid": "swh:1:cnt:1fa0d32c021a24447540ab6dca496948de8088ac"}' \
-H 'Authorization: Token your_token'

        ####__Response__####

            HTTP 200 OK
        """
        return super().update(request, *args, **kwargs)

    @action(methods=['POST', 'GET'], detail=False)
    def bulk_create_files(self, request, *args, **kwargs):
        """
        Bulk create files from command line.

        ####__Request__####

            curl -X POST -H "Content-Type: application/json" \
%(HOST_NAME)s/%(API_PATH)s/files/bulk_create_files/ -d \
'{"swhids": ["swh:1:cnt:1fa0d32c021a24447540ab6dca496948de8088ac", \
"swh:1:cnt:1fa0d32c021a24447540ab6dca496948de8088ad"]}' \
-H 'Authorization: Token your_token'

        ####__Response__####
            Success: HTTP 200 OK
            Error: HTTP 400 BAD REQUEST

        ####__JSON Response__####
            Success:

                {
                    "swhids":
                        {
                            \
'swh:1:cnt:1fa0d32c021a24447540ab6dca496948de8088ac',
                            \
'swh:1:cnt:1fa0d32c021a24447540ab6dca496948de8088ad'
                        }
                }

                or

                {
                    "swhids":
                        {
                            \
'swh:1:cnt:1fa0d32c021a24447540ab6dca496948de8088ac'
                        }
                }

                or

                {"message":"No files created."}

            Error:

            {
                "message": {
                    "swhids": [
                        "Expected a list of items but got type \"str\"."
                    ]
                }
            }

            or

            {
                "message": [
                    "Error while bulk create files. Reason: duplicate key \
value violates unique constraint \"packages_file_swhid_key\"\\nDETAIL:  \
Key (swhid)=(swh:1:cnt:1fa0d32c021a24447540ab6dca496948de8088ad) \
already exists.\\n"
                ]
            }

            or

            {
                "message": [
                    "Procedure request time out"
                ]
            }
        """
        data = request.data
        serializer = self.bulk_create_file_serializer(data=data)
        if serializer.is_valid():
            try:
                swhids = data.get('swhids')
                exist_files = File.objects.in_bulk(
                    id_list=list(swhids), field_name='swhid').keys()
                file_objs = [File(swhid=swhid) for swhid in swhids
                             if swhid not in exist_files]
                res_data = self.create_files(file_objs)
                return Response(data=res_data, status=status.HTTP_200_OK)
            except IntegrityError as err:
                return Response(data={'message': err.args},
                                status=status.HTTP_400_BAD_REQUEST)
        return Response(data={'message': serializer.errors},
                        status=status.HTTP_400_BAD_REQUEST)


class SourceViewSet(ModelViewSet, PackageImportTransactionMixin):
    """
    API endpoint that allows sources to be imported, viewed or edited.
    """
    queryset = Source.objects.all()
    serializer_class = SourceSerializer
    nvr_import_serializer = NVRImportSerializer
    rs_import_serializer = RSImportSerializer
    parser_classes = [JSONParser, FileUploadParser]

    def list(self, request, *args, **kwargs):
        """
        Get a list of sources.

        ####__Request__####

            curl -X GET -H "Content-Type: application/json" \
%(HOST_NAME)s/%(API_PATH)s/sources/  -H 'Authorization: Token your_token'

        ####__Response__####

            HTTP 200 OK
            Content-Type: application/json

            [
                {
                    "id": 1,
                    "checksum": \
"45f5aacb70f6eddac629375bd4739471ece1a2747123338349df069919e909ac",
                    "name": "ansible-2.4.2.0-2.el7",
                    "url": "http://ansible.com",
                    "state": 0,
                    "archive_type": "rpm"
                    "scan_flag": \
"license(scancode-toolkit 30.1.0),copyright(scancode-toolkit 30.1.0)",
                    "component_set": [
                        1
                    ],
                    "license_detections": [
                        "bsd-simplified",
                        "gpl-2.0-plus",
                    ],
                    "copyright_detections": [
                        "Copyright (c) 2005 Ben Gardner <bgardner@wabtec.com>",
                        "Copyright (c) 2013 Fusion-io, Inc.",
                    ]
                }
            ]

        """
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """
        Create a new source.

        ####__Request__####

            curl -X POST -H "Content-Type: application/json" \
%(HOST_NAME)s/%(API_PATH)s/sources/ \
-d '{"name": "xtab.doc.tar.xz", "checksum": \
"597cf23c7b32beaee76dc7ec42f6f04903a3d8239a4b820adf3a3350b93cd65e", \
"archive_type": "rpm"}' \
-H 'Authorization: Token your_token'

        ####__Response__####
            Success: HTTP 200 OK

            Error:
                HTTP 400 BAD REQUEST,

                HTTP 500, Key (name, checksum)=(xtab.doc.tar.xz, \
597cf23c7b32beaee76dc7ec42f6f04903a3d8239a4b820adf3a3350b93cd65e) \
already exists.

        ####__JSON Response__####
            Success:

                {
                    "id": 8,
                    "checksum": \
"597cf23c7b32beaee76dc7ec42f6f04903a3d8239a4b820adf3a3350b93cd65e",
                    "name": "xtab.doc.tar.xz",
                    "url": null,
                    "state": 0,
                    "archive_type": "rpm"
                }

            Error:

                {"archive_type":["This field is required."]}

                Server Error (500)
        """
        return super().create(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """
        Get a specific source.

        ####__Request__####

            curl -X GET -H "Content-Type: application/json" \
%(HOST_NAME)s/%(API_PATH)s/sources/instance_pk/ -H 'Authorization: \
Token your_token'

        ####__Response__####

            HTTP 200 OK
            Content-Type: application/json

            {
                "id": 1,
                "license_detections": [
                    "bsd-simplified",
                    "gpl-2.0-plus",
                ],
                "copyright_detections": [
                    "Copyright (c) 2005 Ben Gardner <bgardner@wabtec.com>",
                    "Copyright (c) 2013 Fusion-io, Inc.",
                ],
                "checksum": \
"45f5aacb70f6eddac629375bd4739471ece1a2747123338349df069919e909ac",
                "name": "ansible-2.4.2.0-2.el7",
                "url": "http://ansible.com",
                "state": 0,
                "archive_type": "rpm"
            }

        """
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """
        Update source from command line.

        ####__Request__####

            curl -X PATCH -H "Content-Type: application/json" \
%(HOST_NAME)s/%(API_PATH)s/sources/instance_pk/ -d \
'{"name": "xtab.doc.tar.xz", "checksum": \
"597cf23c7b32beaee76dc7ec42f6f04903a3d8239a4b820adf3a3350b93cd65e", \
"archive_type": "rpm"}' \
-H 'Authorization: Token your_token'

        ####__Response__####

            HTTP 200 OK
        """
        return super().update(request, *args, **kwargs)

    @action(methods=['post', 'put'], detail=False, url_path='import')
    def import_package(self, request, *args, **kwargs):
        """
        ####__Import a package(multiple packages) from command line.__####

        By default, both `license_scan` and `crypto_scan` will be performed for
        package imports, this can be changed by setting respective option to
        'false'.

        ####__Request form 1: Bulk import with product release and package \
NVRs__####

        ``product_release``: product release name, **OPTIONAL**

        ``package_nvrs``: list of package nvr, **REQUIRED**

        ``license_scan``: boolean option, 'true' if not specified, **OPTIONAL**

        ``copyright_scan``: boolean option, 'true' if not specified, \
**OPTIONAL**

        Example(bulk import two packages with license and copyright scannings):

            curl -X POST -H "Content-Type: application/json" -H \
"Authorization: Token your_token" %(HOST_NAME)s/%(API_PATH)s/sources/import/ \
-d '{"product_release": "satellite-6.9.0", "package_nvrs": \
["ansible-2.4.2.0-2.el7", "fio-3.1-2.el7"]}'

        ####__Response__####

            HTTP 200 OK

            {"ansible-2.4.2.0-2.el7":{"task_id":21},"fio-3.1-2.el7":\
{"task_id":22}}


        ####__Request form 2: Bulk import with productname, version and \
package NVRs in product manifest file.__####

        **Note**: using "manifest parser" API to validate product manifest \
file first, it should contain the following parameters:

        ``prouductname``: product name, **REQUIRED**

        ``version``: version name, **REQUIRED**

        ``src_packages`` list of package nvr, **REQUIRED**

        ####__Request__####

            curl -X PUT -H "Authorization: Token your_token" \
-H 'Content-Disposition: attachment; filename=data.json' \
-d @data.json %(HOST_NAME)s/%(API_PATH)s/sources/import/

        ####__Response__####
            HTTP 200 OK

            {"ansible-2.4.2.0-2.el7":{"task_id":21},"fio-3.1-2.el7":\
{"task_id":22}}
        """
        manifest_file = request.data.get('file')
        manifest_data = None
        if manifest_file:
            try:
                data = parse_manifest_file(manifest_file)
            except RuntimeError as e:
                return Response(
                    data={"message": f"Runtime error: {e.args[0]}"},
                    status=status.HTTP_400_BAD_REQUEST)
            else:
                product_name = data.get("productname")
                version = data.get("version")
                src_packages = data.get("src_packages")
                if product_name and version:
                    release_name = "-".join([product_name, version])
                    product, _ = Product.objects.get_or_create(
                        name=product_name)
                    releases = Release.objects.filter(
                        product=product, version=version)
                    if not releases.exists():
                        Release.objects.create(
                            product=product, version=version,
                            name=release_name, notes=data.get("notes"))
                else:
                    release_name = None
                manifest_data = {
                    "product_release": release_name,
                    "package_nvrs": src_packages
                }
        else:
            release_name = request.data.get('product_release')
            if release_name:
                releases = Release.objects.filter(name=release_name)
                if not releases.exists():
                    # Release could be created once schema is locked down
                    err_msg = f"Product does Not exist: {release_name}."
                    return Response(data={'message': err_msg},
                                    status=status.HTTP_400_BAD_REQUEST)

        data = manifest_data if manifest_data else request.data
        # Import packages based on "API bulk package nvrs import".
        if 'package_nvrs' in request.data:
            serializer = self.nvr_import_serializer(data=data)
        # Import packages for remote source import.
        elif 'rs_comps' in request.data:
            serializer = self.rs_import_serializer(data=request.data)
        else:
            return Response("Missing arguments in request.",
                            status=status.HTTP_400_BAD_REQUEST)

        user_id = request.data.get('owner_id') or request.user.id
        if serializer.is_valid():
            resp = serializer.fork_import_tasks(user_id)
        else:
            return Response(data=serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(data=resp)


class PathViewSet(ModelViewSet, PackageImportTransactionMixin):
    """
    API endpoint that allows Paths to be viewed or edited.
    """
    queryset = Path.objects.all()
    serializer_class = PathSerializer
    bulk_create_path_serializer = BulkCreatePathSerializer

    def list(self, request, *args, **kwargs):
        """
        Get a list of paths.

        ####__Request__####

            curl -X GET -H "Content-Type: application/json" \
%(HOST_NAME)s/%(API_PATH)s/paths/  -H 'Authorization: Token your_token'

        ####__Response__####

            HTTP 200 OK
            Content-Type: application/json
            [
                {
                    "id": 2,
                    "source": "yum.conf.fedora",
                    "file": \
"swh:1:cnt:1fa0d32c021a24447540ab6dca496948de8088ac",
                    "path": "/test1"
                },
                {
                    "id": 3,
                    "source": "zake-0.2.2.tar.gz",
                    "file": \
"swh:1:cnt:1fa0d32c021a24447540ab6dca496948de8088cc",
                    "path": "/test2"
                },
                {
                    "id": 4,
                    "source": "00001-rpath.patch",
                    "file": \
"swh:1:cnt:1fa0d32c021a24447540ab6dca496948de8088dd",
                    "path": "/test3"
                },
                {
                    "id": 5,
                    "source": "0000-Disable-network-based-unit-tests.patch",
                    "file": \
"swh:1:cnt:1fa0d32c021a24447540ab6dca496948de8088ee",
                    "path": "/test4"
                }
            ]
"""
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """
        Create a new path.

        ####__Request__####

            curl -X POST -H "Content-Type: application/json" \
%(HOST_NAME)s/%(API_PATH)s/paths/ \
-d '{"file": "swh:1:cnt:1fa0d32c021a24447540ab6dca496948de8088aa", \
"source": "ab7cf23c7b32beaee76dc7ec42f6f04903a3d8239a4b820adf3a3ss0b93cd652", \
"path": "/test5"} -H 'Authorization: Token your_token'

        ####__Response__####

            Success: HTTP 200 OK
            Error: HTTP 400 BAD REQUEST

        ####__JSON Response__####

            Success:
                {
                  "id": 44496,
                  "source": \
"ab7cf23c7b32beaee76dc7ec42f6f04903a3d8239a4b820adf3a3ss0b93cd652",
                  "file": "swh:1:cnt:1fa0d32c021a24447540ab6dca496948de8088aa",
                  "path": "/test5"
                }

            Error:

                Server Error (500)
        """
        return super().create(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """
        Get a specific path.

        ####__Request__####

            curl -X GET -H "Content-Type: application/json" \
%(HOST_NAME)s/%(API_PATH)s/paths/instance_pk/ -H 'Authorization: \
Token your_token'

        ####__Response__####

            HTTP 200 OK
            Content-Type: application/json
            {
                "id": 2,
                "source": "yum.conf.fedora",
                "file": \
"swh:1:cnt:1fa0d32c021a24447540ab6dca496948de8088ac",
                "path": "/test1"
            }
        """
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """
        Update path from command line.

        ####__Request__####

            curl -X PATCH -H "Content-Type: application/json" \
%(HOST_NAME)s/%(API_PATH)s/paths/instance_pk/ -d \
'{"file": "swh:1:cnt:1fa0d32c021a24447540ab6dca496948de8088aa", \
"source": "ab7cf23c7b32beaee76dc7ec42f6f04903a3d8239a4b820adf3a3ss0b93cd652", \
"path": "/test5"}' -H 'Authorization: Token your_token'

        ####__Response__####

            HTTP 200 OK
        """
        return super().update(request, *args, **kwargs)

    @action(methods=['POST', 'GET'], detail=False)
    def bulk_create_paths(self, request, *args, **kwargs):
        """
        Bulk create paths from command line.

        ####__Request__####

            curl -X POST -H "Content-Type: application/json" \
%(HOST_NAME)s/%(API_PATH)s/paths/bulk_create_paths/ -d \
'{"paths":[{"file": "swh:1:cnt:1fa0d32c021a24447540ab6dca496948de8088aa", \
"source": "ab7cf23c7b32beaee76dc7ec42f6f04903a3d8239a4b820adf3a3ss0b93cd652", \
"path": "/test5"}, {"file": \
"swh:1:cnt:1fa0d32c021a24447540ab6dca496948de8088ff", "source": \
"e01fb480caaa7c7963dcb3328a4700e631bef6070db0e8b685816d220e685f6c", \
"path": "/test6"}]}' \
-H 'Authorization: Token your_token'

        ####__Response__####
            Success: HTTP 200 OK
            Error: HTTP 400 BAD REQUEST

        ####__JSON Response__####
            Success:

                {
                    "paths": [
                        {
                            "id": 5,
                            "source": {
                                "id": 5,
                                "checksum": \
"597cf23c7b32beaee76dc7ec42f6f04903a3d8239a4b820adf3a3350b93cd652",
                                "name": "xtab.doc.tar.xz",
                                "url": null,
                                "state": 0,
                                "archive_type": "rpm"
                            },
                            "file": {
                                "id": 5,
                                "swhid": \
"swh:1:cnt:1fa0d32c021a24447540ab6dca496948de8088ee"
                            },
                            "path": "/test5"
                        },
                        {
                            "id": 6,
                            "source": {
                                "id": 6,
                                "checksum": \
"e01fb480caaa7c7963dcb3328a4700e631bef6070db0e8b685816d220e685f6c",
                                "name": "XStatic-Font-Awesome-4.7.0.0.tar.gz",
                                "url": null,
                                "state": 0,
                                "archive_type": "rpm"
                            },
                            "file": {
                                "id": 6,
                                "swhid": \
"swh:1:cnt:1fa0d32c021a24447540ab6dca496948de8088ff"
                            },
                            "path": "/test6"
                        }
                    ]
                }

                or

                {
                    "paths": [
                        {
                            "id": 5,
                            "source": {
                                "id": 5,
                                "checksum": \
"597cf23c7b32beaee76dc7ec42f6f04903a3d8239a4b820adf3a3350b93cd652",
                                "name": "xtab.doc.tar.xz",
                                "url": null,
                                "state": 0,
                                "archive_type": "rpm"
                            },
                            "file": {
                                "id": 5,
                                "swhid": \
"swh:1:cnt:1fa0d32c021a24447540ab6dca496948de8088ee"
                            },
                            "path": "/test5"
                        }
                    ]
                }

                or

                {"message": "No paths created."}

            Error:

               {
                   "message":[\
"Error while create paths. Reason: duplicate key \
value violates unique constraint \"packages_path_pkey\"\\nDETAIL: \
Key (id)=(5) already exists.\\n"]
                }

                or

               Server Error (500)
        """
        data = request.data
        serializer = self.bulk_create_path_serializer(data=data)
        if serializer.is_valid():
            try:
                source_checksum = data.get("source")
                paths = data.get("paths")
                source = Source.objects.get(checksum=source_checksum)
                res_data = self.create_paths(source, paths)
                return Response(data=res_data, status=status.HTTP_200_OK)
            except IntegrityError as err:
                return Response(data={'message': err.args},
                                status=status.HTTP_400_BAD_REQUEST)
        return Response(data=serializer.errors,
                        status=status.HTTP_400_BAD_REQUEST)


class PackageImportTransactionView(APIView, PackageImportTransactionMixin):
    """
    Package import transaction

    data example:  # noqa
    {
        "swhids": [
            "swh:1:cnt:1fa0d32c021a24447540ab6dca496948de8088aa",
            "swh:1:cnt:1fa0d32c021a24447540ab6dca496948de8088bb"
        ],
        "source": {
            "name": "xtab.doc.tar.xz",
            "checksum": "597cf23c7b32beaee76dc7ec42f6f04903a3d8239a4b820adf3a3350b93cd65e",
            "archive_type": "rpm"
        },
        "paths": [
            {
                "file": "swh:1:cnt:1fa0d32c021a24447540ab6dca496948de8088aa",
                "path": "/test5"
            },
            {
                "file": "swh:1:cnt:1fa0d32c021a24447540ab6dca496948de8088bb",
                "path": "/test6"
            }
        ],
        "component": {
            "name": "jquery",
            "version": "3.5.1",
            "release": "",
            "arch": "",
            "type": YARN,
            "summary_license": "",
            "is_source": True
        }
    }
    """
    def post(self, request, *args, **kwargs):
        try:
            file_path = request.data.get("file_path")
            with open(file_path, encoding='utf-8') as f:
                data = json.load(f)
        except Exception as err:
            return Response(
                data={'message': err.args},
                status=status.HTTP_400_BAD_REQUEST)

        swhids = data.get('swhids')
        source = data.get('source')
        paths = data.get('paths')
        component = data.get('component')
        if not any([swhids, source, paths, component]):
            return Response(
                data={'message': 'No data provided.'},
                status=status.HTTP_400_BAD_REQUEST)

        source_checksum = source.get('checksum')
        qs = Source.objects.filter(checksum=source_checksum)
        if not qs.exists():
            # Retry 10 times to bypass possible concurrency issue.
            max_retries = settings.SAVE_DATA_MAX_RETRIES
            for i in range(max_retries):
                try:
                    # Query files that need to be created.
                    exist_files = File.objects.in_bulk(
                        id_list=list(swhids), field_name='swhid').keys()
                    file_objs = [File(swhid=swhid) for swhid in swhids
                                 if swhid not in exist_files]

                    with transaction.atomic():
                        source_obj = Source.objects.create(**source)
                        self.create_files(file_objs)
                        self.create_paths(source_obj, paths)
                        self.create_component(source_obj, component)
                    break
                except IntegrityError as err:
                    if i == max_retries - 1:
                        return Response(
                            data={'message': f"Failed to process package import transaction data: {err}"},  # noqa
                            status=status.HTTP_400_BAD_REQUEST)
                    else:
                        time.sleep(1 << i)
                        continue
        return Response()


class SaveScanResultView(APIView, SaveScanResultMixin):
    """
    Save package scan result
    """
    def post(self, request, *args, **kwargs):
        try:
            file_path = request.data.get("file_path")
            with open(file_path, encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            return Response(
                data={'message': e.args},
                status=status.HTTP_400_BAD_REQUEST)
        try:
            self.save_scan_result(**data)
            msg = 'Save scan result successfully.'
            return Response(data={'message': msg}, status=status.HTTP_200_OK)

        except RuntimeError as err:
            return Response(
                    data={'message': err.args},
                    status=status.HTTP_400_BAD_REQUEST)


class CheckDuplicateFiles(APIView):
    """
    Check duplicate files, so that we can skip scan step for these files.
    Duplicate files is files that exist in the database, and
    license/copyright should be scanned if needed.
    """
    def post(self, request, *args, **kwargs):
        swhids = request.data.get('swhids')
        license_scan = request.data.get('license_scan')
        copyright_scan = request.data.get('copyright_scan')
        existing_swhids = []
        license_swhids = []
        copyright_swhids = []

        if swhids:
            existing_swhids = File.objects.in_bulk(id_list=list(swhids),
                                                   field_name='swhid').keys()
        if not existing_swhids:
            return Response(data={"duplicate_swhids": existing_swhids})

        # Duplicate files that license scanned.
        if license_scan:
            license_detector = settings.LICENSE_SCANNER
            license_swhids = FileLicenseScan.objects.filter(
                Q(file__swhid__in=existing_swhids,
                  detector=license_detector)).values_list('file__swhid',
                                                          flat=True)
        # Duplicate files that copyright scanned.
        if copyright_scan:
            copyright_detector = settings.COPYRIGHT_SCANNER
            copyright_swhids = FileCopyrightScan.objects.filter(
                Q(file__swhid__in=existing_swhids,
                  detector=copyright_detector)).values_list('file__swhid',
                                                            flat=True)
        # Deduplicate files.
        if license_scan and copyright_scan:
            duplicate_swhids = list(
                set(existing_swhids).intersection(license_swhids,
                                                  copyright_swhids))
        elif license_scan:
            duplicate_swhids = list(
                set(existing_swhids).intersection(license_swhids))
        elif copyright_scan:
            duplicate_swhids = list(
                set(existing_swhids).intersection(copyright_swhids))
        else:
            duplicate_swhids = existing_swhids
        return Response(data={"duplicate_swhids": duplicate_swhids})


class CheckSourceStatus(APIView):
    """
    Check the source existance and scanning flag.
    """
    def post(self, request, *args, **kwargs):
        checksum = request.data.get('checksum')
        qs = Source.objects.filter(checksum=checksum)
        if qs.exists():
            source = qs[0]
            return Response(data={
                "source_api_url":
                    f'{settings.REST_API_PATH}/sources/{source.pk}',
                "source_scan_flag": source.scan_flag})
        return Response(data={"source_api_url": None,
                              "source_scan_flag": None})


class ComponentViewSet(ModelViewSet, PackageImportTransactionMixin):
    """
    API endpoint that allows components to be viewed.
    """
    queryset = Component.objects.all()
    serializer_class = ComponentSerializer

    def list(self, request, *args, **kwargs):
        """
        Get a list of components.

        ####__Request__####

            curl -X GET -H "Content-Type: application/json" \
-H "Authorization: Token your_token" \
%(HOST_NAME)s/%(API_PATH)s/components/

        ####__Response__####

            HTTP 200 OK
            Content-Type: application/json
            [
                {
                    "id": 5,
                    "source": {
                        "id": 5,
                        "checksum": \
"9fb25c78a1aa98a193d9d8b438113624456042f58b3061c851d1f9536d3046b7",
                        "name": "rpm-libs-4.14.3-23.el8",
                        "url": "https://www.redhat.com/",
                        "state": 0,
                        "archive_type": "SRPM",
                        "scan_flag": \
"license(scancode-toolkit 30.1.0),copyright(scancode-toolkit 30.1.0)",
                        "component_set": [
                            5
                        ],
                        "license_detections": [],
                        "copyright_detections": []
                    },
                    "type": "RPM",
                    "name": "rpm-libs",
                    "version": "4.14.3",
                    "release": "23.el8",
                    "arch": "x86_64",
                    "purl": \
"pkg:rpm/redhat/rpm-libs@4.14.3-23.el8?arch=x86_64",
                    "uuid": "852b587a-544d-4baf-8621-e134db891b6a",
                    "summary_license": "",
                    "is_source": false,
                    "synced": true
                },
                ...
            ]
        """
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """
        Get a specific component.

        ####__Request__####

            curl -X GET -H "Content-Type: application/json" \
-H "Authorization: Token your_token" \
%(HOST_NAME)s/%(API_PATH)s/components/instance_pk/

        ####__Response__####

            HTTP 200 OK
            Content-Type: application/json
            {
                "id": 5,
                "source": {
                    "id": 5,
                    "checksum": \
"9fb25c78a1aa98a193d9d8b438113624456042f58b3061c851d1f9536d3046b7",
                    "name": "rpm-libs-4.14.3-23.el8",
                    "url": "https://www.redhat.com/",
                    "state": 0,
                    "archive_type": "SRPM",
                    "scan_flag": \
"license(scancode-toolkit 30.1.0),copyright(scancode-toolkit 30.1.0)",
                    "component_set": [
                        5
                    ],
                    "license_detections": [],
                    "copyright_detections": []
                },
                "type": "RPM",
                "name": "rpm-libs",
                "version": "4.14.3",
                "release": "23.el8",
                "arch": "x86_64",
                "purl": \
"pkg:rpm/redhat/rpm-libs@4.14.3-23.el8?arch=x86_64",
                "uuid": "852b587a-544d-4baf-8621-e134db891b6a",
                "summary_license": "",
                "is_source": false,
                "synced": true
            }
        """
        return super().retrieve(request, *args, **kwargs)


class SaveComponentsView(APIView, SaveComponentsMixin):
    """
    Save container data to database
    """
    def post(self, request, *args, **kwargs):
        try:
            file_path = request.data.get("file_path")
            with open(file_path, encoding='utf-8') as f:
                data = json.load(f)
        except Exception as err:
            return Response(data={'message': err.args},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            self.save_group_components(**data)
            msg = 'Save container components successfully.'
            return Response(data={'message': msg}, status=status.HTTP_200_OK)
        except IntegrityError as err:
            return Response(data={'message': err.args},
                            status=status.HTTP_400_BAD_REQUEST)
