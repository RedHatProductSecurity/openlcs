import time

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.db.utils import IntegrityError

from libs.corgi import CorgiConnector
from packages.models import (
    File,
    Path,
    Source
)
from packages.serializers import BulkFileSerializer
from products.models import (
    Product
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
    def create_paths(source, paths):
        """
        Create source file paths.
        """
        if paths:
            path_objs = [Path(source=source,
                              file=File.objects.get(swhid=p.get('file')),
                              path=p.get('path')) for p in paths]
            Path.objects.bulk_create(path_objs)

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
        connector = CorgiConnector()
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
            # Query license detection that need to be created.
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
            existing_objs = LicenseDetection.objects.all()
            new_objs = [obj for obj in objs if obj not in existing_objs]
            if new_objs:
                LicenseDetection.objects.bulk_create(
                    new_objs, ignore_conflicts=True)

    def update_scan_flag(self, source, scan_type, detector):
        scan_flag = source.scan_flag
        if scan_type == "license_scan":
            new_scan_flag = "license(" + detector + ")"
        else:
            new_scan_flag = "copyright(" + detector + ")"
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
            # Query copyrights detection that need to be created.
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
            existing_objs = CopyrightDetection.objects.all()
            new_objs = [obj for obj in objs if obj not in existing_objs]
            if new_objs:
                CopyrightDetection.objects.bulk_create(
                    objs, ignore_conflicts=True)

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
                license_detector = kwargs.pop('license_detector')
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
                            self.update_scan_flag(
                                    source, "license_scan", license_detector)
                        break
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
                copyright_detector = kwargs.pop('copyright_detector')
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
                            self.update_scan_flag(
                                source, "copyright_scan", copyright_detector)
                        break
                    except IntegrityError as err:
                        if i == max_retries - 1:
                            err_msg = (f'Failed to save copyright scan result.'
                                       f' Reason: {err}')
                            raise RuntimeError(err_msg) from None
                        else:
                            time.sleep(1 << i)
                            continue
