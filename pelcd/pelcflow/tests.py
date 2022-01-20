import logging
import unittest
import tempfile
import shutil
import os

from unittest import mock

from pelcd.pelcflow.tasks import repack_source
from pelcd.pelcflow.tasks import upload_to_deposit
from pelc.libs.deposit import UploadToDeposit


class TestRepackPackage(unittest.TestCase):

    def setUp(self):
        self.engine = {}
        self.unpack_source_dir_path = tempfile.mkdtemp()
        self.tmp_repack_dir_filepath = tempfile.mkdtemp()
        # Create a tmp_repack_source_path contains some file
        for _ in range(3):
            fd, _ = tempfile.mkstemp(dir=self.unpack_source_dir_path)
            with open(fd, 'w', encoding='utf-8') as f:
                f.write("This is a test content")
        self.context = {
            'tmp_filepath': self.tmp_repack_dir_filepath,
            'nvr': "test-nvr",
            'archive_name': 'test-archive.tar',
            'unpack_source_dir_path': self.unpack_source_dir_path
        }

    def test_repack_file(self):
        repack_source(self.context, self.engine)
        tmp_repack_archive_path = os.path.join(
            self.tmp_repack_dir_filepath,
            self.context.get("archive_name"
                             ))
        assert os.path.exists(self.context.get('tmp_repack_archive_path'))
        assert self.context['tmp_repack_archive_path'] == \
               tmp_repack_archive_path

    def tearDown(self):
        shutil.rmtree(self.tmp_repack_dir_filepath)
        shutil.rmtree(self.unpack_source_dir_path)


class TestUploadToDeposit(unittest.TestCase):

    def setUp(self):
        # This tmp path will be deleted in function upload_to_deposit
        # don't need tearDown to destory
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