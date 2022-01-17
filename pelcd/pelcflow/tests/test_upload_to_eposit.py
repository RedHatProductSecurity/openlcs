import logging
import tempfile
from unittest import mock
from unittest import TestCase

from pelcd.pelcflow.tasks import upload_to_deposit
from pelc.libs.deposit import UploadToDeposit


class TestUploadToDeposit(TestCase):

    def setUp(self):
        # This tmp path will be deleted in function upload_to_deposit
        # don't need tearDown to destroy
        tmp_repack_archive_path = tempfile.mkdtemp()
        deposit_url = "http://10.0.211.248:5080/deposit/1"
        self.context = {'tmp_repack_archive_path': tmp_repack_archive_path,
                        'archive_name': "test-archive.tar",
                        'config': {
                            'DEPOSIT_URL': deposit_url,
                            'DEPOSIT_USER': 'test',
                            'DEPOSIT_PASSWORD': 'test'
                        }
                        }
        engine = mock.Mock()
        logging.basicConfig(level=logging.INFO,
                            format='%(name)s - %(levelname)s - %(message)s')
        engine.logger = logging.getLogger()
        self.engine = engine

    @mock.patch.object(UploadToDeposit, 'deposit_archive')
    @mock.patch.object(UploadToDeposit, 'check_deposit_archive_status')
    def testUploadToDeposit(self,
                            mock_check_deposit_archive_status,
                            mock_deposit_archive,
                            ):
        ret_string = '{"deposit_id": "867", ' \
                     '"deposit_status": "deposited", ' \
                     '"deposit_status_detail": null, ' \
                     '"deposit_date": "Dec. 31, 2021, 3:30 a.m."} '
        mock_deposit_archive.return_value = ret_string
        mock_check_deposit_archive_status.return_value = 'done'
        upload_to_deposit(self.context, self.engine)
