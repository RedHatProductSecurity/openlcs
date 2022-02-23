from django.conf import settings
from django.db.utils import IntegrityError

from libs.backoff_strategy import retry

from packages.models import File
from packages.models import Package
from packages.models import Path
from packages.models import Source
from reports.models import LicenseDetection

from packages.serializers import BulkFileSerializer
from packages.serializers import BulkPathSerializer


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

    def save_license_detections(self, path_file_dict, data):
        licenses = [[path_file_dict.get(x[0])] + x[1:] for x in data]
        detector = settings.LICENSE_SCANNER
        objs = [
            LicenseDetection(
                file_id=lic[0],
                license_key=lic[1],
                score=lic[2],
                start_line=lic[3],
                end_line=lic[4],
                rule=lic[6],
                detector=detector)
            for lic in licenses
        ]
        if objs:
            try:
                LicenseDetection.objects.bulk_create(objs)
            except IntegrityError as err:
                err_msg = f'Error while saving licenses. Reason: {err}'
                raise RuntimeError(err_msg) from None

    def save_copyright_detections(self, path_file_dict, data):
        pass

    def save_scan_result(self, **kwargs):
        path_with_swhids = kwargs.pop('path_with_swhids')
        path_with_swhids = list(zip(*path_with_swhids))
        paths, swhids = path_with_swhids[0], path_with_swhids[1]
        file_ids = list(File.objects.filter(swhid__in=swhids).values_list(
                'id', flat=True))
        path_file_dict = dict(zip(paths, file_ids))
        if kwargs.get('license_scan'):
            licenses = kwargs.pop('licenses')
            data = licenses.get('data')
            if not licenses.get('license_exception'):
                self.save_license_detections(path_file_dict, data)
        if kwargs.get('copyright_scan'):
            data = kwargs.pop('copyrights')
            self.save_copyright_detections(path_file_dict, data)
