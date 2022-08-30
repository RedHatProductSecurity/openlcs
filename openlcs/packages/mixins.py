from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q
from django.db.utils import IntegrityError

from libs.backoff_strategy import retry
from libs.corgi_handler import ProductVersion
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


class PackageImportTransactionMixin:
    """
    Package import transaction mixin
    """
    @retry(rand=settings.CREATE_FILES_RAND,
           max_retries=settings.CREATE_FILES_MAX_RETRIES,
           max_wait_interval=settings.CREATE_FILES_MAX_WAIT_INTERVAL)
    def create_files(self, swhids):
        """
        Create source files.
        """
        exist_files = File.objects.in_bulk(id_list=list(swhids),
                                           field_name='swhid').keys()
        objs = [File(swhid=swhid) for swhid in swhids
                if swhid not in exist_files]
        if objs:
            try:
                files = File.objects.bulk_create(objs)
                serializer = BulkFileSerializer({'files': files})
                return serializer.data
            except IntegrityError as err:
                err_msg = f'Error while create files. Reason: {err}'
                raise RuntimeError(err_msg) from None
        else:
            return {'message': 'No files created.'}

    @retry(rand=settings.CREATE_PATHS_RAND,
           max_retries=settings.CREATE_PATHS_MAX_RETRIES,
           max_wait_interval=settings.CREATE_PATHS_MAX_WAIT_INTERVAL)
    def create_paths(self, source, paths):
        """
        Create source file paths.
        """
        swhids = [path.get('file') for path in paths]
        files_dict = File.objects.in_bulk(id_list=list(swhids),
                                          field_name='swhid')
        objs = [Path(source=source, file=files_dict.get(p.get('file')),
                     path=p.get('path')) for p in paths]
        if objs:
            try:
                new_paths = Path.objects.bulk_create(objs)
                serializer = BulkPathSerializer({'paths': new_paths})
                return serializer.data
            except IntegrityError as err:
                err_msg = f'Error while create paths. Reason: {err}'
                raise RuntimeError(err_msg) from None
        else:
            return {'message': 'No paths created.'}

    @staticmethod
    def create_component(source, component_data):
        """
        Create source component.
        """
        # FIXME: similar functions already available, re-use if possible.
        summary_license = component_data.pop("summary_license")
        is_source = component_data.pop("is_source")
        component, _ = Component.objects.update_or_create(
            **component_data,
            defaults={
                'is_source': is_source,
                'summary_license': summary_license,
            })
        component.source = source
        component.save()

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

    def create_product_release(self, product_release):
        """
        Create product and release.
        """
        cp = ProductVersion(settings.CORGI_API_PROD, product_release)
        product_data = cp.get_product_version()
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


class SaveScanResultMixin:
    def __init__(self):
        self.file_license_scan_dict = None
        self.file_copyright_scan_dict = None

    def save_file_license_scan(self, file_ids):
        license_detector = settings.LICENSE_SCANNER
        filters = [Q(file__in=file_ids), Q(detector=license_detector)]
        license_file_ids = FileLicenseScan.objects.filter(
            *filters).values_list('file_id', flat=True)
        new_file_ids = list(set(file_ids).difference(license_file_ids))

        if new_file_ids:
            objs = [
                FileLicenseScan(
                    file_id=file_id,
                    detector=license_detector
                ) for file_id in new_file_ids]
            try:
                FileLicenseScan.objects.bulk_create(objs)
            except IntegrityError as err:
                err_msg = f'Error while saving file license scan. ' \
                          f'Reason: {err}'
                raise RuntimeError(err_msg) from None
        self.file_license_scan_dict = dict(FileLicenseScan.objects.filter(
            *filters).values_list('file_id', 'id'))

    def save_license_detections(self, path_file_dict, data):
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
            try:
                LicenseDetection.objects.bulk_create(objs)
            except IntegrityError as err:
                err_msg = f'Error while saving licenses. Reason: {err}'
                raise RuntimeError(err_msg) from None

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

    def save_file_copyright_scan(self, file_ids):
        copyright_detector = settings.COPYRIGHT_SCANNER
        filters = [Q(file__in=file_ids), Q(detector=copyright_detector)]
        copyright_file_ids = FileCopyrightScan.objects.filter(
            *filters).values_list('file_id', flat=True)
        new_file_ids = list(set(file_ids).difference(copyright_file_ids))

        if new_file_ids:
            objs = [
                FileCopyrightScan(
                    file_id=file_id,
                    detector=copyright_detector
                ) for file_id in new_file_ids]
            try:
                FileCopyrightScan.objects.bulk_create(objs)
            except IntegrityError as err:
                err_msg = f'Error while saving file copyright scan. ' \
                          f'Reason: {err}'
                raise RuntimeError(err_msg) from None
        self.file_copyright_scan_dict = dict(FileCopyrightScan.objects.filter(
            *filters).values_list('file_id', 'id'))

    def save_copyright_detections(self, path_file_dict, data):
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
                        statement=statement["value"],
                        start_line=statement["start_line"],
                        end_line=statement["end_line"]
                    ) for statement in v
                ]
                objs.extend(k_objs)

            if objs:
                try:
                    CopyrightDetection.objects.bulk_create(objs)
                except IntegrityError as err:
                    err_msg = f'Error while saving copyrights. Reason: {err}'
                    raise RuntimeError(err_msg) from None

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
            data = licenses.get('data')
            if not licenses.get('has_exception'):
                with transaction.atomic():
                    # Exist same files in different paths.
                    self.save_file_license_scan(list(set(file_ids)))
                    self.save_license_detections(path_file_dict, data)
                    self.update_scan_flag(source, "license_scan")

        if kwargs.get('copyright_scan'):
            copyrights = kwargs.pop('copyrights')
            data = copyrights.get('data')
            if not copyrights.get('has_exception'):
                with transaction.atomic():
                    self.save_file_copyright_scan(list(set(file_ids)))
                    self.save_copyright_detections(path_file_dict, data)
                    self.update_scan_flag(source, "copyright_scan")


class SaveContainerComponentsMixin:
    def __init__(self):
        self.components = None
        self.release = None

    @staticmethod
    def create_component(component_data):
        summary_license = component_data.pop('license')
        component, _ = Component.objects.update_or_create(
            **component_data,
            defaults={
                "summary_license": summary_license,
            },
        )
        return component

    def build_release_node(self):
        """
        Build release node. For container, if exit release data, will create
        release product tree node, then create a parent product tree node,
        then create some child component product tree node. The parent and
        child components will be component instances.
        """
        # Create container parent components
        container_component = self.create_component(
            self.components.get('container_component')
        )
        # Create release node
        release_ctype = ContentType.objects.get_for_model(Release)
        release_node, _ = ProductTreeNode.objects.get_or_create(
            name=self.release.name,
            content_type=release_ctype,
            object_id=self.release.id,
            parent=None,
        )
        # Create container node
        cnode, _,  = container_component.release_nodes.get_or_create(
            name=container_component.name,
            parent=release_node,
        )
        # Create container child components
        for component_data in self.components.get("components"):
            component = self.create_component(component_data)
            component.release_nodes.get_or_create(
                name=component.name,
                parent=cnode,
            )

    def build_container_node(self):
        """
        Build container node. For container, will create a parent component
        tree node, then create some child component tree node. The parent and
        child components will be component instances.
        """
        # Create container parent components
        container_component = self.create_component(
            self.components.get('container_component')
        )
        # Create container node
        component_ctype = ContentType.objects.get_for_model(Component)
        cnode, _ = ComponentTreeNode.objects.get_or_create(
            name=container_component.name,
            content_type=component_ctype,
            object_id=container_component.id,
            parent=None,
        )
        # Create container child components
        for component_data in self.components.get("components"):
            component = self.create_component(component_data)
            ComponentTreeNode.objects.get_or_create(
                name=component.name,
                parent=cnode,
                content_type=component_ctype,
                object_id=component.id,
            )

    def save_container_components(self, **kwargs):
        self.components = kwargs.pop('components')
        product_release = kwargs.pop('product_release')
        if product_release:
            self.release = Release.objects.filter(name=product_release)[0]
            self.build_release_node()
        else:
            self.build_container_node()
