import json
import os
import time
from distutils.util import strtobool
import django_filters
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django_celery_beat.models import (
    PeriodicTask,
    CrontabSchedule
)
from libs.encrypt_decrypt import encrypt_with_secret_key
from libs.parsers import parse_manifest_file
from packages.mixins import (
    SourceImportMixin,
    SaveScanResultMixin,
)
from packages.models import (
    Component,
    ComponentSubscription,
    File,
    Path,
    Source
)
from authentication.permissions import ReadOnlyModelPermission
from packages.serializers import (
    ComponentSerializer,
    ComponentSubscriptionSerializer,
    FileSerializer,
    NVRImportSerializer,
    PathSerializer,
    RSImportSerializer,
    SourceSerializer,
    ComponentImportSerializer,
    PeriodicTaskSerializer,
    CrontabScheduleSerializer
)
from products.models import (
    Product,
    Release,
    ProductTreeNode,
    ComponentTreeNode
)
from tasks.models import Task
from reports.models import FileCopyrightScan, FileLicenseScan
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import FileUploadParser, JSONParser
from rest_framework.filters import SearchFilter
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet


# Create your views here.
class FileViewSet(ModelViewSet, SourceImportMixin):
    """
    API endpoint that allows files to be viewed or edited.
    """
    queryset = File.objects.all()
    serializer_class = FileSerializer

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


class SourceViewSet(ModelViewSet):
    """
    API endpoint that allows sources to be imported, viewed or edited.
    """
    queryset = Source.objects.all()
    serializer_class = SourceSerializer
    nvr_import_serializer = NVRImportSerializer
    rs_import_serializer = RSImportSerializer
    component_import_serializer = ComponentImportSerializer
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
                    "license_detections":{
                        "public-domain": "%(HOST_NAME)s/%(API_PATH)s/\
licensedetections/?source_id=1&license_key=public-domain",
                        "gpl-2.0-plus": "%(HOST_NAME)s/%(API_PATH)s/\
licensedetections/?source_id=1&license_key=gpl-2.0-plus",
                        "bsd-simplified": "%(HOST_NAME)s/%(API_PATH)s/\
licensedetections/?source_id=1&license_key=bsd-simplified",
                        ...
                    },
                    "copyright_detections": {
                        "Copyright (c) 2013 Fusion-io.": \
"%(HOST_NAME)s/%(API_PATH)s/copyrightdetections/?source_id=1\
&statement=Copyright (c) 2013 Fusion-io.",
                        "Copyright (c) 2010-2017 par": \
"%(HOST_NAME)s/%(API_PATH)s/copyrightdetections/?source_id=1\
&statement=Copyright (c) 2010-2017 par",
                        ...
                    }
                }
            ]

        """
        return super().list(request, *args, **kwargs)

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
                "license_detections":{
                    "public-domain": "%(HOST_NAME)s/%(API_PATH)s/\
licensedetections/?source_id=1&license_key=public-domain",
                    "gpl-2.0-plus": "%(HOST_NAME)s/%(API_PATH)s/\
licensedetections/?source_id=1&license_key=gpl-2.0-plus",
                    "bsd-simplified": "%(HOST_NAME)s/%(API_PATH)s/\
licensedetections/?source_id=1&license_key=bsd-simplified",
                    ...
                },
                "copyright_detections": {
                    "Copyright (c) 2013 Fusion-io.": \
"%(HOST_NAME)s/%(API_PATH)s/copyrightdetections/?source_id=1\
&statement=Copyright (c) 2013 Fusion-io.",
                    "Copyright (c) 2010-2017 par": \
"%(HOST_NAME)s/%(API_PATH)s/copyrightdetections/?source_id=1\
&statement=Copyright (c) 2010-2017 par",
                    ...
                },
                "checksum": \
"45f5aacb70f6eddac629375bd4739471ece1a2747123338349df069919e909ac",
                "name": "ansible-2.4.2.0-2.el7",
                "url": "http://ansible.com",
                "state": 0,
                "archive_type": "rpm"
            }

        """
        return super().retrieve(request, *args, **kwargs)

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

        ``priority``: string option, specific task priority. Value can be \
one of the "high", "medium", "low". "low" if not specified, **OPTIONAL**

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
                    return Response(
                        data={'message': err_msg},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        data = manifest_data if manifest_data else request.data
        # Import packages based on "API bulk package nvrs import".
        if 'package_nvrs' in data:
            serializer = self.nvr_import_serializer(data=data)
        # Import packages for remote source import.
        elif 'rs_comps' in data:
            serializer = self.rs_import_serializer(data=data)
        elif 'components' in data:
            serializer = self.component_import_serializer(data=data)
        else:
            return Response(
                "Missing arguments in request.",
                status=status.HTTP_400_BAD_REQUEST,
            )
        if serializer.is_valid():
            parent_task_id = request.data.get('parent_task_id', '')
            # For child task, token will be autubot user's token.
            if parent_task_id:
                token = request.data.get('token')
            # For parent task, token will be user's token.
            else:
                token = encrypt_with_secret_key(
                    request.headers['Authorization'].split()[-1],
                    os.getenv("TOKEN_SECRET_KEY")
                )
            resp = serializer.fork_import_tasks(
                request.user.id, parent_task_id, token)
        else:
            return Response(
                data=serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(data=resp)


class PathViewSet(ModelViewSet, SourceImportMixin):
    """
    API endpoint that allows Paths to be viewed or edited.
    """
    queryset = Path.objects.all()
    serializer_class = PathSerializer

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


class PackageImportTransactionView(APIView, SourceImportMixin):
    """
    Package import transaction

    data example:
    {
        "task_id": "7030f5da-7282-4960-a716-7d8d8328b9c2",
        "source_info":{
            "product_release": "rhel-8.9",
            "swhids":[
                "swh:1:cnt:1fa0d32c021a24447540ab6dca496948de8088aa",
                "swh:1:cnt:1fa0d32c021a24447540ab6dca496948de8088bb"
            ],
            "source":{
                "name":"xtab.doc.tar.xz",
                "checksum": \
"597cf23c7b32beaee76dc7ec42f6f04903a3d8239a4b820adf3a3350b93cd65e",
                "archive_type":"rpm"
            },
            "paths":[
                {
                    "file": \
"swh:1:cnt:1fa0d32c021a24447540ab6dca496948de8088aa",
                    "path":"/test5"
                },
                {
                    "file": \
"swh:1:cnt:1fa0d32c021a24447540ab6dca496948de8088bb",
                    "path":"/test6"
                }
            ],
            "component":{
                "name":"jquery",
                "version":"3.5.1",
                "release":"",
                "arch":"",
                "type":"YARN",
                "summary_license":"",
                "is_source":true
            }
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
                data={'message': err.args}, status=status.HTTP_400_BAD_REQUEST
            )

        task_id = data.get('task_id')
        source_info = data.get('source_info')
        swhids = source_info.get('swhids')
        source = source_info.get('source')
        paths = source_info.get('paths')
        component = source_info.get('component')
        product_release = source_info.get('product_release')
        if not any([swhids, source, paths, component]):
            return Response(
                data={'message': 'No data provided.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # get task object for update
        task_obj = Task.objects.get(meta_id=task_id)

        source_checksum = source.get('checksum')
        qs = Source.objects.filter(checksum=source_checksum)
        if not qs.exists():
            # Retry 10 times to bypass possible concurrency issue.
            max_retries = settings.SAVE_DATA_MAX_RETRIES
            for i in range(max_retries):
                # avoid create Source object failed because checksum
                # already exists caused by concurrency
                if qs.exists():
                    break

                try:
                    file_objs = []
                    # Query files that need to be created.
                    if swhids:
                        exist_files = File.objects.in_bulk(
                            id_list=list(swhids), field_name='swhid').keys()
                        file_objs = [File(swhid=swhid) for swhid in swhids
                                     if swhid not in exist_files]

                    with transaction.atomic():
                        source_obj = Source.objects.create(**source)
                        if file_objs:
                            # limit the number of objects created in one
                            #  query, which reduces memory consumption
                            File.objects.bulk_create(
                                file_objs,
                                batch_size=1000)
                        if paths:
                            self.create_paths(source_obj, paths)
                        if component:
                            component_obj = Component.\
                                update_or_create_component(component)
                            component_obj.source = source_obj
                            component_obj.save()
                            if product_release:
                                ProductTreeNode.build_release_node(
                                    component, product_release)

                    break
                except IntegrityError as err:
                    if i == max_retries - 1:
                        return Response(
                            data={'message': f"Failed to process package import transaction data: {err}"},  # noqa
                            status=status.HTTP_400_BAD_REQUEST)
                    else:
                        time.sleep(1 << i)
                        continue

        # link task to exist Source object
        task_obj.content_object = qs[0]
        task_obj.save()

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
        detector = request.data.get('detector')
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
            license_swhids = FileLicenseScan.objects.filter(
                Q(file__swhid__in=existing_swhids,
                  detector=detector)).values_list('file__swhid', flat=True)
        # Duplicate files that copyright scanned.
        if copyright_scan:
            copyright_swhids = FileCopyrightScan.objects.filter(
                Q(file__swhid__in=existing_swhids,
                    detector=detector)).values_list('file__swhid', flat=True)
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


class ComponentFilter(django_filters.FilterSet):
    """Class that filters queries to Component list views."""

    name = django_filters.CharFilter(field_name='name', lookup_expr='iexact')
    type = django_filters.CharFilter(
            field_name='type', lookup_expr='icontains')
    version = django_filters.CharFilter(
            field_name='version', lookup_expr='iexact')
    release = django_filters.CharFilter(
            field_name='release', lookup_expr='iexact')
    arch = django_filters.CharFilter(field_name='arch', lookup_expr='iexact')
    purl = django_filters.CharFilter(
            field_name='purl', lookup_expr='icontains')
    uuid = django_filters.CharFilter(field_name='uuid', lookup_expr='iexact')
    summary_license = django_filters.CharFilter(
            field_name='summary_license', lookup_expr='iexact')
    is_source = django_filters.BooleanFilter(field_name='is_source')
    source__name = django_filters.CharFilter(lookup_expr='iexact')
    source__state = django_filters.NumberFilter()
    source__archive_type = django_filters.CharFilter(lookup_expr='iexact')
    source__scan_flag = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = Component

        fields = (
            'name', 'type', 'version', 'release', 'arch', 'purl',
            'uuid', 'summary_license', 'is_source',
        )


class ComponentViewSet(ModelViewSet):
    """
    API endpoint that allows components to be viewed.
    """

    queryset = Component.objects.all()
    serializer_class = ComponentSerializer
    filter_backends = (
        django_filters.rest_framework.DjangoFilterBackend,
        SearchFilter,
    )
    filter_class = ComponentFilter
    search_fields = ["type", "name", "version", "release", "arch"]

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
                        "archive_type": "rpm",
                        "scan_flag": \
"license(scancode-toolkit 30.1.0),copyright(scancode-toolkit 30.1.0)",
                        "component_set": [
                            5
                        ],
                        "license_detections":{
                            "public-domain": "%(HOST_NAME)s/%(API_PATH)s/\
licensedetections/?source_id=1&license_key=public-domain",
                            "gpl-2.0-plus": "%(HOST_NAME)s/%(API_PATH)s/\
licensedetections/?source_id=1&license_key=gpl-2.0-plus",
                            "bsd-simplified": "%(HOST_NAME)s/%(API_PATH)s/\
licensedetections/?source_id=1&license_key=bsd-simplified",
                            ...
                        },
                        "copyright_detections": {
                            "Copyright (c) 2013 Fusion-io.": \
"%(HOST_NAME)s/%(API_PATH)s/copyrightdetections/?source_id=1\
&statement=Copyright (c) 2013 Fusion-io.",
                            "Copyright (c) 2010-2017 par": \
"%(HOST_NAME)s/%(API_PATH)s/copyrightdetections/?source_id=1\
&statement=Copyright (c) 2010-2017 par",
                            ...
                        }
                    },
                    "provides": [],
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
                },
                ...
            ]

        ####__Request__####

            curl -X GET -H "Content-Type: application/json" \
-H "Authorization: Token your_token" \
%(HOST_NAME)s/%(API_PATH)s/components/?name=fio&type= \
&version=&release=&arch=&purl=&uuid=&summary_license=& \
is_source=unknown&source__name=& \
source__state=&source__archive_type=&source__scan_flag=

        ####__Supported query params__####

        ``name``: String, the component name.

        ``type``: String, the component type.

        ``version``: String, the component version.

        ``release``: String, the component release.

        ``arch``: String, the component arch.

        ``purl``: String, the component purl.

        ``uuid``: String, the component uuid.

        ``summary_license``: String, the component summary_license.

        ``is_source``: Boolean, the component is_source.

        ``from_corgi``: Boolean, True if component is from component registry

        ``sync_status``: String, possible values includes "synced", \
"unsynced" and "sync_failed".

        ``sync_failure_reason``: String, reason of the failure, only \
applicable when sync_status is "sync_failed".

        ``source__name``: String, the source's name.

        ``source__state``: String, the source's state.

        ``source__archive_type``: String, the source's archive_type.

        ``source__scan_flag``: String, the source's scan_flag.


        ####__Response__####

            HTTP 200 OK
            Content-Type: application/json
            [
                {
                    "id": 1,
                    "source": {
                        "id": 1,
                        "name": "fio-3.1-2.el7.src.rpm",
                        "url": "http://git.kernel.dk/?p=fio.git;a=summary",
                        "checksum": "65ddad4b0831a46d9064d96e80283618c04bdxxx",
                        "state": 0,
                        "archive_type": "rpm",
                        "scan_flag": "copyright(scancode-toolkit 30.1.0)",
                        "component_set": [
                            1
                        ],
                        "license_detections":{
                            "public-domain": "%(HOST_NAME)s/%(API_PATH)s/\
licensedetections/?source_id=1&license_key=public-domain",
                            "gpl-2.0-plus": "%(HOST_NAME)s/%(API_PATH)s/\
licensedetections/?source_id=1&license_key=gpl-2.0-plus",
                            "bsd-simplified": "%(HOST_NAME)s/%(API_PATH)s/\
licensedetections/?source_id=1&license_key=bsd-simplified",
                            ...
                        },
                        "copyright_detections": {
                            "Copyright (c) 2013 Fusion-io.": \
"%(HOST_NAME)s/%(API_PATH)s/copyrightdetections/?source_id=1\
&statement=Copyright (c) 2013 Fusion-io.",
                            "Copyright (c) 2010-2017 par": \
"%(HOST_NAME)s/%(API_PATH)s/copyrightdetections/?source_id=1\
&statement=Copyright (c) 2010-2017 par",
                            ...
                        }
                    },
                    "type": "RPM",
                    "provides": [],
                    "name": "fio",
                    "version": "3.1",
                    "release": "2.el7",
                    "arch": "src",
                    "purl": "",
                    "uuid": "de3da5cc-bbf2-4953-9e33-084506706073",
                    "summary_license": "GPLv2",
                    "is_source": true,
                    "from_corgi": false,
                    "sync_status": "unsynced",
                    "sync_failure_reason": null
                }
            ]

        ####__Request__####
            curl -X GET -H "Content-Type: application/json" \
-H "Authorization: Token your_token" \
%(HOST_NAME)s/%(API_PATH)s/components/?search=fio

        ####__Supported search field__####

        NOTE: ``fio`` denotes the value of field ``name``

        ``name``: String, the component name.

        ``type``: String, the component type.

        ``version``: String, the component version.

        ``release``: String, the component release.

        ``arch``: String, the component arch.

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
                    "archive_type": "rpm",
                    "scan_flag": \
"license(scancode-toolkit 30.1.0),copyright(scancode-toolkit 30.1.0)",
                    "component_set": [
                        5
                    ],
                    "license_detections":{
                        "public-domain": "\
licensedetections/?source_id=1&license_key=public-domain",
                        "gpl-2.0-plus": "%(HOST_NAME)s/%(API_PATH)s/\
licensedetections/?source_id=1&license_key=gpl-2.0-plus",
                        "bsd-simplified": "%(HOST_NAME)s/%(API_PATH)s/\
licensedetections/?source_id=1&license_key=bsd-simplified",
                        ...
                    },
                    "copyright_detections": {
                        "Copyright (c) 2013 Fusion-io.": \
"%(HOST_NAME)s/%(API_PATH)s/copyrightdetections/?source_id=1\
&statement=Copyright (c) 2013 Fusion-io.",
                        "Copyright (c) 2010-2017 par": \
"%(HOST_NAME)s/%(API_PATH)s/copyrightdetections/?source_id=1\
&statement=Copyright (c) 2010-2017 par",
                        ...
                    }
                },
                "type": "RPM",
                "provides": [],
                "name": "rpm-libs",
                "version": "4.14.3",
                "release": "23.el8",
                "arch": "x86_64",
                "purl": \
"pkg:rpm/redhat/rpm-libs@4.14.3-23.el8?arch=x86_64",
                "uuid": "852b587a-544d-4baf-8621-e134db891b6a",
                "summary_license": "",
                "is_source": false,
            }
        """
        return super().retrieve(request, *args, **kwargs)


class CheckDuplicateImport(APIView):
    """
    Check duplicate container/component/module import,
    so that we can skip duplicate import for these files.
    Duplicate import means reimport a container/component/module
    that exists in the database.
    """
    def post(self, request, *args, **kwargs):
        results = dict()
        data = request.data
        parent = data.get('parent', '')
        if parent != '' and data.get('type') == 'OCI':
            return Response(data={
                    'results': results})
        imported_components = Component.objects.filter(
                name=data.get('name', ''),
                version=data.get('version', ''),
                release=data.get('release', ''),
                arch=data.get('arch', ''),
                type=data.get('type', ''),
        )
        serializer = ComponentSerializer(imported_components, many=True)
        serializer_data = serializer.data

        if serializer_data and len(serializer_data) == 1:
            obj = serializer_data[0]
            source_ready = 'source' in obj and \
                obj['source'] is None and parent != ''
            if source_ready:
                return Response(data={
                        'results': results})
            obj_url = 'http://{}/rest/v1/components/{}/'.format(
                settings.HOSTNAME, obj.get('id', -1))
            results['obj_url'] = obj_url
        return Response(data={
                'results': results})


class SaveComponentsView(APIView):
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
            components = data.get('components')
            product_release = data.get('product_release')
            component_type = data.get('component_type')

            # Create container/module parent components
            parent_component_data = components.pop(component_type)[0]
            if product_release:
                ProductTreeNode.build_release_node(
                    parent_component_data, product_release)
            ComponentTreeNode.build_component_tree(
                parent_component_data, components)

            msg = 'Save container components successfully.'
            return Response(data={'message': msg}, status=status.HTTP_200_OK)
        except IntegrityError as err:
            return Response(data={'message': err.args},
                            status=status.HTTP_400_BAD_REQUEST)


class ComponentSubscriptionViewSet(ModelViewSet):
    """
    API endpoint that allows ComponentSubscription to be viewed or edited.
    """
    queryset = ComponentSubscription.objects.all()
    serializer_class = ComponentSubscriptionSerializer
    permission_classes = [ReadOnlyModelPermission]

    def get_queryset(self):
        active = self.request.query_params.get('active', None)
        if active is not None:
            queryset = self.queryset.filter(active=strtobool(active))
        else:
            queryset = self.queryset

        return queryset

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve a specified component subscription instance.

        ####__Request__####

            curl -X GET -H "Content-Type: application/json" \
-H 'Authorization: Token your_token' \
%(HOST_NAME)s/%(API_PATH)s/subscriptions/id/

        ####__Response__####

            HTTP 200 OK
            Content-Type: application/json
            {
            "id": 1,
            "name": "ansible_automation_platform:2.2",
            "query_params": {
                "ofuri": "o:redhat:ansible_automation_platform:2.2"
            },
            "component_purls": [
                "pkg:rpm/redhat/python-pyjwt@1.7.1-8.el9pc?arch=src",
                "pkg:rpm/redhat/python-webencodings@0.5.1-3.el9pc?arch=src",
                "pkg:oci/aap-must-gather-container-source?tag=0.0.1-216.1",
                "pkg:oci/automation-controller-operator-container",
                "pkg:oci/automation-controller-container-source",
                "pkg:oci/ee-29-container-source?tag=1.0.0-219.1",
                "pkg:oci/automation-hub-container-source?tag=4.5.2-31.1",
                "pkg:oci/ansible-python-toolkit-container-source",
                "pkg:oci/ansible-builder-container-source?tag=1.1.0-99.1",
                "pkg:oci/automation-hub-web-container-source?tag=4.5.2-29.1",
                "pkg:oci/ee-minimal-container-source?tag=1.0.0-234.1",
                "pkg:oci/ee-supported-container-source?tag=1.0.0-196.1",
                "pkg:oci/platform-resource-runner-container-source",
                "pkg:rpm/redhat/receptor@1.3.0-1.el9ap?arch=src",
                "...",
                "<list-is-too-long-and-omitted...>",
                "...",
            ],
            "active": true,
            "created_at": "2023-01-18T09:35:55.582000Z",
            "updated_at": "2023-01-18T10:52:37.775419Z"
            }
        """
        return super().retrieve(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        """
        Get a list of component subscription instances.

        ####__Supported query params__####

        ``active``: boolean, status of subscription, "true" or "false".

        ####__Response__####

            HTTP 200 OK
            Content-Type: application/json
            [
                {
                    "count": 1,
                    "next": null,
                    "previous": null,
                    "results": [
                        {
                            "active": true,
                            "component_purls": [],
                            "created_at": "2023-02-23T07:25:40.530352Z",
                            "id": 1,
                            "name": "ubi9-container-9.0.0-1640.1669730845",
                            "query_params": {
                                "nvr": "ubi9-container-9.0.0-1640.1669730845"
                            },
                            "updated_at": "2023-02-23T07:25:40.530371Z"
                        }
                    ]
                }
            ]
        """
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """
        Create a component subscription instance. Restricted to \
admin users only.

        ####__Request__####

            curl -X POST -H "Content-Type: application/json" \
-H 'Authorization: Token your_token' \
%(HOST_NAME)s/%(API_PATH)s/subscriptions/ \
-d '{"name": "mysubscription", "query_params": \
{"ofuri": "corgi-stream-ofuri"}}'

        ####__Required field in data__####

        ``name``: String, the subscription name.

        ``query_params``: Dict, a key-value store denoting supported \
query params of the corgi `component` api endpoint.

        ####__Response__####

            Success: HTTP 201 Created
            {
                "id": 6,
                "name": "mysubscription",
                "query_params": {
                    "ofuri": "corgi-stream-ofuri"
                },
                "component_purls": [],
                "active": true,
                "created_at": "2023-01-19T02:55:12.582557Z",
                "updated_at": "2023-01-19T02:55:12.582576Z"
            }

            Error: HTTP 400 BAD REQUEST or HTTP 403 Forbidden

        """
        return super().create(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        """
        This function is customized to allow "append" mode by default when
        updating `component_purls` field.
        """
        subscription = self.get_object()
        component_purls = request.data.get("component_purls")
        source_purls = request.data.get("source_purls")
        update_mode = request.data.get("update_mode", "append")

        if component_purls is not None:
            subscription.update_component_purls(component_purls,
                                                update_mode)
        if source_purls is not None:
            subscription.update_source_purls(source_purls, update_mode)

        # do some clean up and delegate rest of updates to super()
        request_data = request.data.copy()
        request_data.pop("component_purls", None)
        request_data.pop("source_purls", None)
        if "update_mode" in request_data:
            request_data.pop("update_mode")

        serializer = self.get_serializer(
                subscription, data=request_data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    def patch(self, request, *args, **kwargs):
        """
        Update an existing component subscription instance. Restricted to \
admin users only.

        ####__Request__####

            curl -X PATCH -H "Content-Type: application/json" \
-H 'Authorization: Token your_token' \
%(HOST_NAME)s/%(API_PATH)s/subscriptions/6/ \
-d '{"name": "mysubscription", "query_params": \
{"ofuri": "corgi-stream-ofuri"}, "active": "false"}'

        ####__Fields that can be updated__####

        ``name``: String, the subscription name.

        ``query_params``: Dict, a key-value store denoting supported \
query params of the corgi `component` api endpoint.

        ``active``: Boolean, set to false will disable the subscription.

        ####__Response__####

            Success: HTTP 200 OK
            {
                "id": 6,
                "name": "mysubscription",
                "query_params": "{ofuri: corgi-stream-ofuri}",
                "component_purls": [],
                "active": false,
                "created_at": "2023-01-19T02:55:12.582557Z",
                "updated_at": "2023-01-19T03:51:13.878047Z"
            }
            Error: HTTP 400 BAD REQUEST or HTTP 403 Forbidden

        """
        return self.partial_update(request, *args, **kwargs)


class GetSyncedPurls(APIView):
    """
    Get the scanned and synced component purls of a subscription.
    """
    def get(self, request, *args, **kwargs):
        purls = []
        if subscription_id := request.query_params.get('subscription_id'):
            qs = ComponentSubscription.objects.filter(pk=subscription_id)
            if qs.exists():
                subscription = qs[0]
                components = subscription.get_synced_components()
                purls = [component.purl for component in components]
        else:
            components = Component.objects.filter(sync_status='synced')
            purls = [component.purl for component in components]
        return Response(data={"purls": purls})


class PeriodicTaskViewSet(ModelViewSet):
    """
    API endpoint that allows PeriodicTask to be viewed or edited
    """
    queryset = PeriodicTask.objects.all()
    serializer_class = PeriodicTaskSerializer

    def get_queryset(self):
        name = self.request.query_params.get('name', None)
        if name is not None:
            queryset = self.queryset.filter(name=name)
        else:
            queryset = self.queryset

        return queryset

    def list(self, request, *args, **kwargs):
        """
        Get a list of periodic tasks.
        ####__Supported query params__####

        ``name``: String.The periodic task name.
        ####__Response__####

            HTTP 200 OK
            Content-Type: application/json
            [
                {
                    "count": 1,
                    "next": null,
                    "previous": null,
                    "results": [
                        {
                            "id": 1,
                            "name": "run_corgi_sync",
                            "task": "openlcsd.flow.periodic_tasks.run_corgi_sync", # noqa
                            "one_off": false,
                            "last_run_at": null,
                            "date_changed": "2023-06-12T07:32:25.487194Z",
                            "crontab": 2,
                            "priority": null,
                            "enabled": true
                        }
                    ]
                }
            ]
        """
        return super().list(request, *args, **kwargs)

    def patch(self, request, *args, **kwargs):
        """
        Update an existing periodic task.
        ####__Request__####

            curl -X PATCH -H "Content-Type: application/json" \
-H 'Authorization: Token your_token' \
%(HOST_NAME)s/%(API_PATH)s/periodictask/1/ \
-d '{"one_off":true, "crontab":3}'

        ####__Fields that can be updated__####

        ``crontab``: The id of Crontab Schedule to run the task on.

        ``one_off``: If True, the schedule will only run the task a single \
                time.

        ####__Response__####

            Success: HTTP 200 OK
            {
                "id":1,
                "name":"run_corgi_sync",
                "task":"openlcsd.flow.periodic_tasks.run_corgi_sync",
                "one_off":false,
                "last_run_at":null,
                "date_changed":"2023-06-12T08:26:39.554036Z",
                "crontab":3,
                "priority":null,
                "enabled":true
            }
            Error: HTTP 400 BAD REQUEST or HTTP 403 Forbidden

        """
        periodictask = self.get_object()
        request_data = request.data.copy()
        serializer = self.get_serializer(
                periodictask, data=request_data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)


class CrontabScheduleViewSet(ModelViewSet):
    """
    API endpoint that allows CrontabSchedule to be viewed or edited
    """
    queryset = CrontabSchedule.objects.all()
    serializer_class = CrontabScheduleSerializer

    def list(self, request, *args, **kwargs):
        """
        List the existing crontab schedules.
        ####__Response__####

            HTTP 200 OK
            Content-Type: application/json
            [
                {
                    "count": 1,
                    "next": null,
                    "previous": null,
                    "results": [
                        {
                            "id": 1,
                            "minute": "0",
                            "hour": "0",
                            "day_of_week": "*",
                            "day_of_month": "*",
                            "month_of_year": "*"
                        }
                    ]
                }
            ]
        """
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """
        Create new crontab schedules.

        ####__Request__####

            curl -X POST -H "Content-Type: application/json" \
-H 'Authorization: Token your_token' \
%(HOST_NAME)s/%(API_PATH)s/crontabschedule/ \
-d '{"minute": "munite", "hour":"hour"}'

        ####__Required field in data__####

        ``minute``: String. Cron Minutes to Run. Use "*" for "all".

        ``hour``: String. Cron Hours to Run. Use "*" for "all".

        ``day_of_week``: String. Cron Days Of The Week to Run. Use "*" for \
                "all". Sunday is 0 or 7, Monday is 1.

        ``day_of_month``: String. Cron Days Of The Month to Run. Use "*" for \
                "all".

        ``month_of_year``: String. Cron Months (1-12) Of The Year to Run. Use \
                "*" for "all"

        ####__Response__####

            Success: HTTP 201 Created
            {
                "id":3,
                "minute":"1",
                "hour":"1",
                "day_of_week":"*",
                "day_of_month":"*",
                "month_of_year":"*"
            }

            Error: HTTP 400 BAD REQUEST or HTTP 403 Forbidden

        """
        return super().create(request, *args, **kwargs)
