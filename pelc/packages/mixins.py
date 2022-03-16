from django.conf import settings
from django.db import transaction
from django.db.utils import IntegrityError

from libs.backoff_strategy import retry
from packages.models import File
from packages.models import Package
from packages.models import Path
from packages.models import Source
from packages.serializers import BulkFileSerializer
from packages.serializers import BulkPathSerializer
from reports.models import CopyrightDetection
from reports.models import FileCopyrightScan
from reports.models import FileLicenseScan
from reports.models import LicenseDetection


class PackageImportTransactionMixin:
    """
    Package import transaction mixin
    """
    @retry(rand=settings.CREATE_FILES_RAND,
           max_retries=settings.CREATE_FILES_MAX_RETRIES,
           max_wait_interval=settings.CREATE_FILES_MAX_WAIT_INTERVAL)
    def create_files(self, swhids):
        """
        Create files.
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
    def create_paths(self, source_checksum, paths):
        """
        Create paths.
        """
        # Three SQL queries will be run here.
        # One is to get the Source object, one is to get all File objects.
        # One is to created Path objects.
        source = Source.objects.get(checksum=source_checksum)
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
    def create_package(source_checksum, package):
        """
        Create package.
        """
        source, _ = Source.objects.get_or_create(checksum=source_checksum)
        Package.objects.get_or_create(source=source, **package)


class SaveScanResultMixin:
    def __init__(self):
        self.file_license_scans = None
        self.file_copyright_scans = None

    def save_file_license_scan(self, file_ids):
        license_detector = settings.LICENSE_SCANNER
        objs = [
            FileLicenseScan(
                file_id=file_id,
                detector=license_detector
            ) for file_id in file_ids]

        if objs:
            try:
                self.file_license_scans = FileLicenseScan.objects.bulk_create(
                    objs)
            except IntegrityError as err:
                err_msg = f'Error while saving file license scan. ' \
                          f'Reason: {err}'
                raise RuntimeError(err_msg) from None

    def save_license_detections(self, path_file_dict, data):
        id_mapping_dict = {item.file.id: item.id for item in
                           self.file_license_scans}
        licenses = [[id_mapping_dict.get(path_file_dict.get(x[0]))] + x[1:] for
                    x in data]
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
        if objs:
            try:
                LicenseDetection.objects.bulk_create(objs)
            except IntegrityError as err:
                err_msg = f'Error while saving licenses. Reason: {err}'
                raise RuntimeError(err_msg) from None

    def save_file_copyright_scan(self, file_ids):
        copyright_detector = settings.COPYRIGHT_SCANNER
        objs = [
            FileCopyrightScan(
                file_id=file_id,
                detector=copyright_detector
            ) for file_id in file_ids]

        if objs:
            try:
                self.file_copyright_scans = \
                    FileCopyrightScan.objects.bulk_create(objs)
            except IntegrityError as err:
                err_msg = f'Error while saving file copyright scan. ' \
                          f'Reason: {err}'
                raise RuntimeError(err_msg) from None

    def save_copyright_detections(self, path_file_dict, data):
        id_mapping_dict = {item.file.id: item.id for item in
                           self.file_copyright_scans}
        raw_data = data.get('detail_copyrights')
        copyrights = dict(
            (id_mapping_dict.get(path_file_dict.get(k)), v) for (k, v) in
            raw_data.items())
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

        if kwargs.get('license_scan'):
            licenses = kwargs.pop('licenses')
            data = licenses.get('data')
            if not licenses.get('has_exception'):
                with transaction.atomic():
                    # Exist same files in different paths.
                    self.save_file_license_scan(list(set(file_ids)))
                    self.save_license_detections(path_file_dict, data)

        if kwargs.get('copyright_scan'):
            copyrights = kwargs.pop('copyrights')
            data = copyrights.get('data')
            if not copyrights.get('has_exception'):
                with transaction.atomic():
                    self.save_file_copyright_scan(list(set(file_ids)))
                    self.save_copyright_detections(path_file_dict, data)
