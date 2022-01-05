from django.conf import settings
from django.db.utils import IntegrityError

from libs.backoff_strategy import retry

from packages.models import File
from packages.models import Package
from packages.models import Path
from packages.models import Source

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
    def create_paths(self, paths):
        """
        Create paths.
        """
        objs = [Path(source=Source.objects.get(checksum=p.get('source')),
                     file=File.objects.get(swhid=p.get('file')),
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
    def create_package(package):
        """
        Create package.
        """
        source, _ = Package.objects.get_or_create(
            checksum=package.pop('source'))
        Package.objects.get_or_create(source=source, **package)
