import os
from io import StringIO
import json
import shutil
import tempfile
import warnings
from unittest import TestCase
from kobo.shortcuts import run
from django.conf import settings
from libs.download import BrewBuild
from libs.parsers import parse_manifest_file
from libs.scanner import LicenseScanner
from libs.scanner import CopyrightScanner
from libs.unpack import UnpackArchive


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
        os.environ.setdefault(
                'DJANGO_SETTINGS_MODULE', 'openlcs.openlcs.settings')
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
        result = None
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


class TestParseManifestFile(TestCase):

    def setUp(self):
        # data with valid form
        valid_data = {
            'release': {
                'productname': 'testproduct',
                'version': '1.0.0',
                'notes': 'sample notes',
                'containers': [],
                'src_packages': [
                    'nvr1', 'nvr2', 'nvr3'
                ]}
        }
        # missing required field 'release'
        invalid_data1 = {
            'product': 'foo'
        }
        # missing required field 'version'
        invalid_data2 = {
            'release': {
                'productname': 'testproduct',
                'src_packages': ['nvr1', 'nvr2', 'nvr3']
            }
        }
        # 'src_packages' is of incorrect type(should be array)
        invalid_data3 = {
            'release': {
                'productname': 'testproduct',
                'version': '1.0.0',
                'src_packages': {},
            }
        }
        self.non_existent_file = '/path/to/non-existent'
        self.valid_json = json.dumps(valid_data)
        self.invalid_json_form1 = json.dumps(invalid_data1)
        self.invalid_json_form2 = json.dumps(invalid_data2)
        self.invalid_json_form3 = json.dumps(invalid_data3)

    def test_parse_non_existent_file(self):
        with self.assertRaises(RuntimeError) as exception_context:
            parse_manifest_file(self.non_existent_file)
            self.assertEqual(
                str(exception_context.exception),
                f'{self.non_existent_file} is not a file'
            )

    def test_parse_invalid_file(self):
        with self.assertRaises(RuntimeError):
            parse_manifest_file(self.invalid_json_form1)
            parse_manifest_file(self.invalid_json_form2)
            parse_manifest_file(self.invalid_json_form3)

    def test_parse_valid_file(self):
        # Transfer json string to file-like object before parsing
        result = parse_manifest_file(StringIO(self.valid_json))
        self.assertIn('productname', result)
        self.assertIn('version', result)


class TestLicenseScan(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = {
            # Update below path to your virtualenv path in local
            'SCANCODE_CLI': '/opt/app-root/bin/scancode',
        }

    def setUp(self):
        self.src_dir = tempfile.mkdtemp(prefix='scan_')

    def test_scan(self):
        # Prepare a text file for license scanning
        license_file = os.path.join(self.src_dir, 'license_file')
        with open(license_file, "w", encoding="utf-8") as license_file:
            license_file.write("http://www.gzip.org/zlib/zlib_license.html")
        scanner = LicenseScanner(
            src_dir=self.src_dir,
            config=TestLicenseScan.config)
        (licenses, errors, has_exception) = scanner.scan(scanner='scancode')

        self.assertEqual(licenses[0][0], 'license_file')
        self.assertEqual(licenses[0][1], 'zlib')
        self.assertEqual(licenses[0][2], 100.0)
        self.assertEqual(licenses[0][3], 1)
        self.assertEqual(licenses[0][4], 1)
        self.assertEqual(errors, [])
        self.assertFalse(has_exception)

    def tearDown(self):
        shutil.rmtree(self.src_dir, ignore_errors=True)


class TestCopyrightScan(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = {
            # Update below path to your virtualenv path in local
            'SCANCODE_CLI': '/opt/app-root/bin/scancode',
        }

    def setUp(self):
        self.src_dir = tempfile.mkdtemp(prefix='scan_')

    def test_scan(self):
        # Prepare a text file for copyright scanning
        copyright_file = os.path.join(self.src_dir, 'copyright_file')
        statement = "Copyright (c) 2022 Qingmin Duanmu <qduanmu@test.com>"
        with open(copyright_file, "w", encoding="utf-8") as copyright_file:
            copyright_file.write(statement)
        scanner = CopyrightScanner(
            src_dir=self.src_dir,
            config=TestCopyrightScan.config)
        (copyrights, errors, has_exception) = scanner.scan(scanner='scancode')
        detail = copyrights.get('detail_copyrights')
        detail_key = next(iter(detail))
        self.assertEqual(detail_key, 'copyright_file')
        self.assertEqual(detail[detail_key][0], {
            'value': statement, 'start_line': 1, 'end_line': 1}
        )
        self.assertEqual(errors, [])
        self.assertFalse(has_exception)

    def tearDown(self):
        shutil.rmtree(self.src_dir, ignore_errors=True)
