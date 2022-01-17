import os
import shutil
import tempfile
from unittest import TestCase

from pelcd.pelcflow.tasks import repack_source


class TestRepackPackage(TestCase):

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
