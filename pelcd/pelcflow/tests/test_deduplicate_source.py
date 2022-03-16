import os
import shutil
import tempfile
from unittest import mock
from unittest import TestCase


from pelcd.pelcflow import tasks


class TestDeduplicateSource(TestCase):

    def setUp(self) -> None:
        # Create temp unpack path for deduplicate.
        self.src_dest_dir = tempfile.mkdtemp()
        self.context = {
            "src_dest_dir": self.src_dest_dir,
            "source_info": {}
        }
        self.engine = mock.Mock()

        # Create temp unpack data for deduplicate.
        # Create three files, the fist one is duplicate files, the second
        # one is new file, the third one is soft link of the second one.
        src_file = None
        paths = []
        for i in range(3):
            if i < 2:
                fd, tmp_file = tempfile.mkstemp(
                    dir=self.src_dest_dir)
                with open(fd, 'w', encoding="utf-8") as f:
                    f.write(f"This is a test content {i} for duplicate")
                if i == 1:
                    src_file = tmp_file
                paths.append(
                    os.path.join(self.src_dest_dir, tmp_file))
            else:
                tmp_file = tempfile.mktemp(dir=self.src_dest_dir)
                os.symlink(src_file, tmp_file)
        self.paths = paths

    @mock.patch.object(tasks, 'get_data_using_post')
    def test_deduplicate_source(self, mock_get_data_using_post):
        swhid_dict = {"duplicate_swhids": [
            "swh:1:cnt:c0de67c68fac3a78be782a7197f4072d8f2c8668"]}
        mock_get_data_using_post.return_value = swhid_dict
        tasks.deduplicate_source(self.context, self.engine)

        # swhids only contain not duplicate swhids
        assert self.context['source_info']['swhids'] == [
            "swh:1:cnt:cc81ecacefe341bcb52cde42a7cd4a8f82058862"
        ]

        # paths contain all paths object except soft link.
        context_source_paths = self.context['source_info']['paths']
        source_paths = [
            {
                "file": "swh:1:cnt:c0de67c68fac3a78be782a7197f4072d8f2c8668",
                "path": self.paths[0]
            },
            {
                "file": "swh:1:cnt:cc81ecacefe341bcb52cde42a7cd4a8f82058862",
                "path": self.paths[1]
            }
        ]
        self.assertCountEqual(context_source_paths,  source_paths)

    def tearDown(self) -> None:
        shutil.rmtree(self.src_dest_dir)
