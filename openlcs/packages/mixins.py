import time

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q
from django.db.utils import IntegrityError

from libs.corgi import CorgiConnector
from packages.models import (
    Component,
    File,
    Path,
    Source
)
from packages.serializers import BulkFileSerializer, BulkPathSerializer
from products.models import (
    Product,
    Release,
    ComponentTreeNode,
    ProductTreeNode,
)
from reports.models import (
    CopyrightDetection,
    FileCopyrightScan,
    FileLicenseScan,
    LicenseDetection
)


class SourceImportMixin:
    """
    Package import transaction mixin
    """

    @staticmethod
    def create_files(file_objs):
        """
        Create source files.
        """
        if file_objs:
            files = File.objects.bulk_create(file_objs)
            serializer = BulkFileSerializer({'files': files})
            return serializer.data
        else:
            return {'message': 'No files created.'}

    @staticmethod
    def create_paths(source, paths):
        """
        Create source file paths.
        """
        if paths:
            path_objs = [Path(source=source,
                              file=File.objects.get(swhid=p.get('file')),
                              path=p.get('path')) for p in paths]
            paths = Path.objects.bulk_create(path_objs)
            serializer = BulkPathSerializer({'paths': paths})
            return serializer.data
        else:
            return {'message': 'No paths created.'}

    @staticmethod
    def create_product(product_name, description=""):

        p, _ = Product.objects.update_or_create(
            name=product_name,
            display_name=product_name,
            defaults={
                "description": description,
            },
        )
        return p

    def create_product_release(self, name):
        """
        Create product and release.
        """
        connector = CorgiConnector(settings.CORGI_API_PROD)
        product_data = connector.get_product_version(name)
        if product_data:
            product_name = product_data.get('products')[0].get('name')
            product_name_release = product_data.get("name")
            product_release = product_name_release[len(product_name)+1:]
            description = product_data.get("description", "")

            # Create product instance
            product = self.create_product(product_name, description)
            # Create release
            product.add_release(
                name=product_name_release,
                version=product_release,
                notes=description,
            )


class SaveComponentsMixin:
    def __init__(self):
        self.components = None
        self.release = None

    @staticmethod
    def create_component(component_data):
        summary_license = "" if component_data.get('summary_license') is None\
            else component_data['summary_license']
        defaults = {"summary_license": summary_license}
        if "is_source" in component_data:
            defaults.update({
                'is_source': component_data.get("is_source")
            })
        component, _ = Component.objects.update_or_create(
            name=component_data.get('name'),
            version=component_data.get('version'),
            release=component_data.get('release'),
            arch=component_data.get('arch'),
            type=component_data.get('type'),
            defaults=defaults
        )
        return component

    def build_release_node(self, release_component):
        """
        Build release tree nodes, each component in a release will be a node,
        for a container/module, the release will be its parent node.
        """
        # Create release node
        release_ctype = ContentType.objects.get_for_model(Release)
        release_node, _ = ProductTreeNode.objects.get_or_create(
            content_type=release_ctype,
            object_id=self.release.id,
            parent=None,
        )

        # Create release component node
        release_component.release_nodes.get_or_create(
            parent=release_node,
        )

    def build_component_node(self, parent_component):
        """
        Build container/module component nodes. For container/module, the nodes
        include a parent node and its children nodes.
        """
        # Create container/module node
        component_ctype = ContentType.objects.get_for_model(Component)
        cnode, _ = ComponentTreeNode.objects.get_or_create(
            content_type=component_ctype,
            object_id=parent_component.id,
            parent=None,
        )
        # Create child components
        for _, components in self.components.items():
            for component_data in components:
                component = self.create_component(component_data)
                component.component_nodes.get_or_create(
                    parent=cnode,
                )

    def save_group_components(self, **kwargs):
        self.components = kwargs.get('components')
        product_release = kwargs.get('product_release')
        component_type = kwargs.get('component_type')

        # Create container/module parent components
        parent_component_data = self.components.pop(component_type)[0]
        parent_component = self.create_component(parent_component_data)

        if product_release:
            self.release = Release.objects.filter(name=product_release)[0]
            self.build_release_node(parent_component)
        self.build_component_node(parent_component)


class SaveScanResultMixin:
    def __init__(self):
        self.file_license_scan_dict = None
        self.file_copyright_scan_dict = None

    def save_file_license_scan(self, new_file_ids, license_detector):
        if new_file_ids:
            objs = [
                FileLicenseScan(file_id=file_id, detector=license_detector)
                for file_id in new_file_ids]
            file_license_scan_list = FileLicenseScan.objects.bulk_create(objs)
            new_file_license_scan_dict = {item.file_id: item.id
                                          for item in file_license_scan_list}
            self.file_license_scan_dict.update(new_file_license_scan_dict)

    def save_license_detections(self, path_file_dict, data, license_detector):
        licenses = [
            [self.file_license_scan_dict.get(path_file_dict.get(x[0]))] + x[1:]
            for x in data]
        if licenses:
            objs = [
                LicenseDetection(
                    file_scan_id=lic[0],
                    license_key=lic[1],
                    score=lic[2],
                    start_line=lic[3],
                    end_line=lic[4],
                    rule=lic[6],
                ) for lic in licenses
            ]
            LicenseDetection.objects.bulk_create(objs)

    def update_scan_flag(self, source, scan_type):
        scan_flag = source.scan_flag
        if scan_type == "license_scan":
            new_scan_flag = "license(" + settings.LICENSE_SCANNER + ")"
        else:
            new_scan_flag = "copyright(" + settings.COPYRIGHT_SCANNER + ")"
        if scan_flag and new_scan_flag not in scan_flag:
            scan_flag = scan_flag + "," + new_scan_flag
        else:
            scan_flag = new_scan_flag
        source.scan_flag = scan_flag
        source.save(update_fields=['scan_flag'])

    def save_file_copyright_scan(
            self, new_file_ids, copyright_detector):
        if new_file_ids:
            objs = [
                FileCopyrightScan(file_id=file_id, detector=copyright_detector)
                for file_id in new_file_ids]
            file_copyright_scan_list = FileCopyrightScan.objects.bulk_create(
                objs)
            new_file_copyright_scan_dict = {
                item.file_id: item.id for item in file_copyright_scan_list}
            self.file_copyright_scan_dict.update(new_file_copyright_scan_dict)

    def save_copyright_detections(
            self, path_file_dict, data, copyright_detector):
        # TODO: Schema needs an update for summary copyrights
        raw_data = data.get('detail_copyrights')
        copyrights = dict(
            (self.file_copyright_scan_dict.get(path_file_dict.get(k)), v) for
            (k, v) in raw_data.items())
        if copyrights:
            objs = []
            for k, v in copyrights.items():
                k_objs = [
                    CopyrightDetection(
                        file_scan_id=k,
                        statement=statement["copyright"],
                        start_line=statement["start_line"],
                        end_line=statement["end_line"]
                    ) for statement in v
                ]
                objs.extend(k_objs)

            if objs:
                CopyrightDetection.objects.bulk_create(objs)

    def save_scan_result(self, **kwargs):
        path_with_swhids = kwargs.pop('path_with_swhids')
        path_with_swhids = list(zip(*path_with_swhids))
        paths, swhids = path_with_swhids[0], path_with_swhids[1]
        swhid_file_dict = dict(File.objects.filter(
            swhid__in=swhids).values_list('swhid', 'id'))
        file_ids = [swhid_file_dict.get(swhid) for swhid in swhids]
        path_file_dict = dict(zip(paths, file_ids))
        source_checksum = kwargs.pop('source_checksum')
        source = Source.objects.get(checksum=source_checksum)

        if kwargs.get('license_scan'):
            licenses = kwargs.pop('licenses')
            if not licenses.get('has_exception'):
                data = licenses.get('data')
                license_detector = settings.LICENSE_SCANNER
                filters = [Q(file__in=file_ids), Q(detector=license_detector)]

                # Retry max_retries times to bypass possible concurrency issue.
                max_retries = settings.SAVE_DATA_MAX_RETRIES
                for i in range(max_retries):
                    try:
                        self.file_license_scan_dict = dict(
                            FileLicenseScan.objects.filter(
                                *filters).values_list('file_id', 'id'))
                        license_file_ids = self.file_license_scan_dict.keys()
                        new_file_ids = list(
                            set(file_ids).difference(license_file_ids))

                        with transaction.atomic():
                            # Exist same files in different paths.
                            self.save_file_license_scan(
                                new_file_ids, license_detector)
                            self.save_license_detections(
                                path_file_dict, data, license_detector)
                            self.update_scan_flag(source, "license_scan")
                    except IntegrityError as err:
                        if i == max_retries - 1:
                            err_msg = (f'Failed to save license scan result.'
                                       f' Reason: {err}')
                            raise RuntimeError(err_msg) from None
                        else:
                            time.sleep(1 << i)
                            continue

        if kwargs.get('copyright_scan'):
            copyrights = kwargs.pop('copyrights')
            if not copyrights.get('has_exception'):
                data = copyrights.get('data')
                copyright_detector = settings.COPYRIGHT_SCANNER
                filters = [Q(file__in=file_ids),
                           Q(detector=copyright_detector)]

                # Retry 5 times to bypass possible concurrency issue.
                max_retries = settings.SAVE_DATA_MAX_RETRIES
                for i in range(max_retries):
                    try:
                        self.file_copyright_scan_dict = dict(
                            FileCopyrightScan.objects.filter(
                                *filters).values_list('file_id', 'id'))
                        copyright_file_ids = \
                            self.file_copyright_scan_dict.keys()
                        new_file_ids = list(
                            set(file_ids).difference(copyright_file_ids))

                        with transaction.atomic():
                            self.save_file_copyright_scan(
                                new_file_ids, copyright_detector)
                            self.save_copyright_detections(
                                path_file_dict, data, copyright_detector)
                            self.update_scan_flag(source, "copyright_scan")
                    except IntegrityError as err:
                        if i == max_retries - 1:
                            err_msg = (f'Failed to save copyright scan result.'
                                       f' Reason: {err}')
                            raise RuntimeError(err_msg) from None
                        else:
                            time.sleep(1 << i)
                            continue
