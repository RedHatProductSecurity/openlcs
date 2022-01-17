import os
import shutil
import tempfile
from unittest import mock
from unittest import TestCase


from pelcd.pelcflow import tasks


class TestDeduplicateSource(TestCase):

    def setUp(self) -> None:
        # Create temp unpack path for deduplicate.
        self.unpack_source_dir_path = tempfile.mkdtemp()
        self.context = {
            "unpack_source_dir_path": self.unpack_source_dir_path
        }
        self.engine = {}

        # Create temp unpack data for deduplicate.
        # Create three files, the fist one is duplicate files, the second
        # one is new file, the third one is soft link of the second one.
        src_file = None
        paths = []
        for i in range(3):
            if i < 2:
                fd, tmp_file = tempfile.mkstemp(
                    dir=self.unpack_source_dir_path)
                with open(fd, 'w', encoding="utf-8") as f:
                    f.write(f"This is a test content {i} for duplicate")
                if i == 1:
                    src_file = tmp_file
                paths.append(
                    os.path.join(self.unpack_source_dir_path, tmp_file))
            else:
                tmp_file = tempfile.mktemp(dir=self.unpack_source_dir_path)
                os.symlink(src_file, tmp_file)
        self.paths = paths

    @mock.patch.object(tasks, 'check_duplicate_files')
    def test_deduplicate_source(self, mock_check_duplicate_files):
        swhid_dict = {"existing_swhids": [
            "swh:1:cnt:c0de67c68fac3a78be782a7197f4072d8f2c8668"]}
        mock_check_duplicate_files.return_value = swhid_dict
        tasks.deduplicate_source(self.context, self.engine)

        # swhids only contain not duplicate swhids
        assert self.context.get('swhids') == [
            "swh:1:cnt:cc81ecacefe341bcb52cde42a7cd4a8f82058862"
        ]

        # paths contain all paths object except soft link.
        assert self.context.get('paths') == [
            {
                "file": "swh:1:cnt:c0de67c68fac3a78be782a7197f4072d8f2c8668",
                "path": self.paths[0]
            },
            {
                "file": "swh:1:cnt:cc81ecacefe341bcb52cde42a7cd4a8f82058862",
                "path": self.paths[1]
            }
        ]

    def tearDown(self) -> None:
        shutil.rmtree(self.unpack_source_dir_path)
