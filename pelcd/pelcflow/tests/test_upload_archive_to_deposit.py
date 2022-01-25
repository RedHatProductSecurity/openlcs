import tempfile
from unittest import mock
from unittest import TestCase

from pelcd.pelcflow import tasks
from pelc.libs.deposit import UploadToDeposit


class TestUploadArchiveToDeposit(TestCase):

    def setUp(self):
        # This tmp path will be deleted in function upload_to_deposit
        # don't need tearDown to destroy
        tmp_repack_archive_path = tempfile.mkdtemp()
        deposit_url = "http://10.0.211.248:5080/deposit/1"
        self.context = {
            'tmp_repack_archive_path': tmp_repack_archive_path,
            'archive_name': "test-archive.tar",
            'config': {
                'DEPOSIT_URL': deposit_url,
                'DEPOSIT_USER': 'test',
                'DEPOSIT_PASSWORD': 'test'
            }
        }
        self.engine = mock.Mock()

    @mock.patch.object(tasks, 'get_data_using_post')
    @mock.patch.object(UploadToDeposit, 'deposit_archive')
    @mock.patch.object(UploadToDeposit, 'check_deposit_archive_status')
    @mock.patch.object(UploadToDeposit, 'get_deposit_id')
    def testUploadArchiveToDeposit(self, mock_get_data_using_post,
                                   mock_check_deposit_archive_status,
                                   mock_deposit_archive,
                                   mock_get_deposit_id):
        ret_string = '{"deposit_id": "867", ' \
                     '"deposit_status": "deposited", ' \
                     '"deposit_status_detail": null, ' \
                     '"deposit_date": "Dec. 31, 2021, 3:30 a.m."} '
        mock_get_data_using_post.return_value = {"source_exist": False}
        mock_deposit_archive.return_value = ret_string
        mock_check_deposit_archive_status.return_value = 'done'
        mock_get_deposit_id.return_value = 867
        tasks.upload_archive_to_deposit(self.context, self.engine)
