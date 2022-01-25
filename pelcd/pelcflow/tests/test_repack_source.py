import os
import shutil
import tempfile
from unittest import mock
from unittest import TestCase

from pelcd.pelcflow import tasks


class TestRepackSource(TestCase):

    def setUp(self):
        self.engine = mock.Mock()
        self.src_dest_dir = tempfile.mkdtemp()
        self.tmp_repack_dir_filepath = tempfile.mkdtemp()
        # Create a tmp_repack_source_path contains some file
        for _ in range(3):
            fd, _ = tempfile.mkstemp(dir=self.src_dest_dir)
            with open(fd, 'w', encoding='utf-8') as f:
                f.write("This is a test content")
        self.context = {
            "archive_name": 'test-archive-1.0.tar',
            "src_dest_dir": self.src_dest_dir,
            "source_info": {"source": {"checksum": mock.Mock()}},
            "package_nvr": "test-archive-1.0"
        }

    @mock.patch.object(tasks, 'get_data_using_post')
    def test_repack_source(self, mock_get_data_using_post):
        mock_get_data_using_post.return_value = {"source_exist": False}
        tasks.repack_source(self.context, self.engine)
        assert os.path.exists(self.context.get('tmp_repack_archive_path'))

    def tearDown(self):
        shutil.rmtree(self.tmp_repack_dir_filepath)
        shutil.rmtree(self.src_dest_dir)
