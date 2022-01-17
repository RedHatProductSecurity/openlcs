import os
import shutil
import tempfile
import warnings
from unittest import TestCase
from unittest import skip
from kobo.shortcuts import run
from django.conf import settings

from libs.unpack import UnpackArchive
from libs.download import BrewBuild


@skip("Skip temporarily due to PVLEGAL-1905")
class TestUnpack(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = {
            # Update below path to your virtualenv path in local
            'EXTRACTCODE_CLI': '/opt/app-root/bin/extractcode',
        }
        cls.brew_url = 'http://download.eng.bos.redhat.com/brewroot'
        warnings.simplefilter('ignore', ResourceWarning)

    def test_extract(self):
        archive_name = 'atool-0.39.0-5.el7eng.src.rpm'
        archive_path = '/vol/rhel-7/packages/atool/0.39.0/5.el7eng/src/'
        archive_url = TestUnpack.brew_url + archive_path + archive_name

        tmp_dir = tempfile.mkdtemp(prefix='download_')
        cmd = f'wget {archive_url}'
        run(cmd, stdout=False, can_fail=True, workdir=tmp_dir)

        source_archives = os.listdir(tmp_dir)
        self.assertEqual(len(source_archives), 1)
        self.assertEqual(source_archives[0], archive_name)

        src_filepath = os.path.join(tmp_dir, archive_name)
        dest_dir = tempfile.mkdtemp(prefix='unpack_')
        ua = UnpackArchive(
            config=TestUnpack.config,
            src_file=src_filepath,
            dest_dir=dest_dir)
        ua.extract()
        shutil.rmtree(tmp_dir, ignore_errors=True)
        extracted_files = os.listdir(dest_dir)
        self.assertEqual(len(extracted_files), 2)
        shutil.rmtree(dest_dir, ignore_errors=True)

    def test_unpack_archives_using_extractcode(self):
        archive_name = 'python-attrs-18.2.0-1.el7eng.src.rpm'
        archive_path = '/vol/rhel-7/packages/python-attrs/18.2.0/1.el7eng/src/'
        archive_url = TestUnpack.brew_url + archive_path + archive_name

        tmp_dir = tempfile.mkdtemp(prefix='download_')
        cmd = f'wget {archive_url}'
        run(cmd, stdout=False, can_fail=True, workdir=tmp_dir)
        src_filepath = os.path.join(tmp_dir, archive_name)
        ua = UnpackArchive(
            config=TestUnpack.config,
            src_file=src_filepath,
            dest_dir=tmp_dir)
        ua.unpack_archives_using_extractcode(tmp_dir)

        unpacked_sources = os.listdir(tmp_dir)
        self.assertEqual(len(unpacked_sources), 1)
        is_replaced = os.path.isdir(src_filepath)
        self.assertTrue(is_replaced)
        shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_unpack_archives_using_atool(self):
        archive_name = 'vertx-unit-4.1.5.redhat-00002-docs.zip'
        archive_path = '/packages/io.vertx-vertx-unit/4.1.5.redhat_00002/' + \
                       '1/maven/io/vertx/vertx-unit/4.1.5.redhat-00002/'
        archive_url = TestUnpack.brew_url + archive_path + archive_name

        tmp_dir = tempfile.mkdtemp(prefix='download_')
        cmd = f'wget {archive_url}'
        run(cmd, stdout=False, can_fail=True, workdir=tmp_dir)
        src_filepath = os.path.join(tmp_dir, archive_name)
        ua = UnpackArchive(
            config=TestUnpack.config,
            src_file=src_filepath,
            dest_dir=tmp_dir)
        ua.unpack_archives_using_atool(tmp_dir, top_dir=True)

        unpacked_sources = os.listdir(tmp_dir)
        self.assertEqual(len(unpacked_sources), 1)
        is_replaced = os.path.isdir(src_filepath)
        self.assertTrue(is_replaced)
        shutil.rmtree(tmp_dir, ignore_errors=True)


class TestDownloadFromBrew(TestCase):

    def setUp(self):
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pelc.pelc.settings')
        self.test_package_nvr = 'python-futures-3.1.1-5.el7'
        self.context = {'config': {'BREW_DOWNLOAD': settings.BREW_DOWNLOAD,
                                   'BREW_WEBSERVICE': settings.BREW_WEBSERVICE,
                                   'BREW_WEBURL': settings.BREW_WEBURL
                                   },
                        'package_nvr': self.test_package_nvr
                        }

    def test_download_build_source(self):
        """
        When use kobo.shortcuts.run function to download
        file will throw warnings
        https://stackoverflow.com/questions/48160728/resourcewarning-unclosed-socket-in-python-3-unit-test # noqa
        """
        warnings.filterwarnings(
            action="ignore", message="unclosed", category=ResourceWarning
        )
        try:
            brew_build = BrewBuild(self.context.get('config'))
            build = brew_build.get_build(
                package_nvr=self.context.get('package_nvr')
            )
            result = brew_build.download_source(build)
            test_file_name = self.test_package_nvr + '.src.rpm'
            test_file_path = os.path.join(result, test_file_name)
            self.assertTrue(os.path.exists(test_file_path))
        finally:
            shutil.rmtree(result, ignore_errors=True)
