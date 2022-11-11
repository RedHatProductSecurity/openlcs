import os
from io import StringIO
import json
import shutil
import tempfile
import warnings
from unittest import mock
from unittest import TestCase
from kobo.shortcuts import run
from django.conf import settings

from libs.corgi_handler import ParentComponentsAsync
from libs.kojiconnector import KojiConnector
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
            'EXTRACTCODE_CLI': os.getenv("OLCS_EXTRACTCODE_CLI",
                                         "/opt/app-root/bin/extractcode"),
        }
        cls.koji_download = os.getenv(
            'KOJI_DOWNLOAD',
            'https://kojipkgs.fedoraproject.org/')
        warnings.simplefilter('ignore', ResourceWarning)

    def test_extract(self):
        archive_name = 'atool-0.39.0-5.el7eng.src.rpm'
        archive_path = '/vol/rhel-7/packages/atool/0.39.0/5.el7eng/src/'
        archive_url = TestUnpack.koji_download + archive_path + archive_name

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
        archive_url = TestUnpack.koji_download + archive_path + archive_name

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
        archive_url = TestUnpack.koji_download + archive_path + archive_name

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
        self.context = {'config': {'KOJI_DOWNLOAD': settings.KOJI_DOWNLOAD,
                                   'KOJI_WEBSERVICE': settings.KOJI_WEBSERVICE,
                                   'KOJI_WEBURL': settings.KOJI_WEBURL
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
            koji_connector = KojiConnector(self.context.get('config'))
            build = koji_connector.get_build_extended(
                package_nvr=self.context.get('package_nvr')
            )
            result = koji_connector.download_source(build)
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
            'SCANCODE_CLI': os.getenv("OLCS_SCANCODE_CLI",
                                      "/opt/app-root/bin/scancode"),
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
            'SCANCODE_CLI': os.getenv("OLCS_SCANCODE_CLI",
                                      "/opt/app-root/bin/scancode"),
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


class TestComponents(TestCase):
    def setUp(self):
        warnings.simplefilter('ignore', RuntimeWarning)
        os.environ.setdefault(
                'DJANGO_SETTINGS_MODULE', 'openlcs.openlcs.settings')
        corgi_api_prod = os.getenv("CORGI_API_PROD")
        self.links = [
            f'{corgi_api_prod}components?purl=pkg%3Arpm/redhat/glibc-minimal-langpack%402.28-151.el8%3Farch%3Ds390x',  # noqa
            f'{corgi_api_prod}components?purl=pkg%3Arpm/redhat/openssl-libs%401.1.1g-15.el8_3%3Farch%3Ds390x',  # noqa
            f'{corgi_api_prod}components?purl=pkg:npm/@jest/fake-timers@27.2.0'  # noqa
        ]
        self.components_data = [
            {
                'uuid': 'fe7f82c1-db81-4045-84d6-c81a9da8d145',
                'type': 'RPM',
                'name': 'glibc-minimal-langpack',
                'version': '2.28',
                'release': '151.el8',
                'arch': 's390x',
                'summary_license': '',
                'synced': True
            },
            {
                'uuid': 'fe7f82c1-db81-4045-84d6-c81a9da8d146',
                'type': 'RPM',
                'name': 'openssl-libs',
                'version': '1.1.1g',
                'release': '15.el8_3',
                'arch': 's390x',
                'summary_license': '',
                'synced': True
            },
            {
                'uuid': 'fe7f82c1-db81-4045-84d6-c81a9da8d147',
                'type': 'NPM',
                'name': '@jest/fake-timers',
                'version': '27.2.0',
                'release': '',
                'arch': '',
                'summary_license': '',
                'synced': True
            },
            {
                'uuid': 'bb7e0e10-0a68-4bae-a490-3ff491cb1b78',
                'type': 'OCI',
                'name': "grc-ui-api-container",
                'version': '13',
                'release': 'v2.4.0',
                'arch': 's390x',
                'summary_license': '',
                'synced': True
            }
        ]
        self.group_components_data = {
            'RPM': [
                {
                    'uuid': 'fe7f82c1-db81-4045-84d6-c81a9da8d145',
                    'type': 'RPM',
                    'name': 'glibc-minimal-langpack',
                    'version': '2.28',
                    'release': '151.el8',
                    'arch': 's390x',
                    'summary_license': '',
                    'synced': True
                },
                {
                    'uuid': 'fe7f82c1-db81-4045-84d6-c81a9da8d146',
                    'type': 'RPM',
                    'name': 'openssl-libs',
                    'version': '1.1.1g',
                    'release': '15.el8_3',
                    'arch': 's390x',
                    'summary_license': '',
                    'synced': True
                }
            ],
            'NPM': [
                {
                    'uuid': 'fe7f82c1-db81-4045-84d6-c81a9da8d147',
                    'type': 'NPM',
                    'name': '@jest/fake-timers',
                    'version': '27.2.0',
                    'release': '',
                    'arch': '',
                    'summary_license': '',
                    'synced': True
                }
            ],
            'OCI': [
                {
                    'uuid': 'bb7e0e10-0a68-4bae-a490-3ff491cb1b78',
                    'type': 'OCI',
                    'name': "grc-ui-api-container",
                    'version': '13',
                    'release': 'v2.4.0',
                    'arch': 's390x',
                    'summary_license': '',
                    'synced': True
                }
            ]
        }
        base_url = f"{corgi_api_prod}components"
        parent_nvr = 'grc-ui-api-container-13-v2.4.0'
        self.container_components = ParentComponentsAsync(
            base_url, parent_nvr)

    @mock.patch.object(
        ParentComponentsAsync, 'get_component_data_from_corgi')
    def test_get_component_data_1(
            self, mock_get_component_data_from_corgi):
        mock_get_component_data_from_corgi.return_value = \
            self.components_data[0]
        component = self.container_components.get_component_data(
            self.links[0])
        self.assertEqual(component, self.components_data[0])

    @mock.patch.object(
        ParentComponentsAsync, 'get_component_data_from_corgi')
    @mock.patch.object(ParentComponentsAsync, 'parse_component_link')
    def test_get_component_data_2(
            self, mock_get_component_data_from_corgi,
            mock_parse_component_link):
        mock_get_component_data_from_corgi.return_value = {}
        mock_parse_component_link.return_value = \
            self.components_data[1]
        component = self.container_components.get_component_data(
            self.links[1])
        self.assertEqual(component, self.components_data[1])

    @mock.patch.object(
        ParentComponentsAsync, 'get_component_data_from_corgi')
    @mock.patch.object(ParentComponentsAsync, 'parse_component_link')
    def test_get_component_data_3(
            self, mock_get_component_data_from_corgi,
            mock_parse_component_link):
        mock_get_component_data_from_corgi.return_value = {}
        mock_parse_component_link.return_value = \
            self.components_data[2]
        component = self.container_components.get_component_data(
            self.links[2])
        self.assertEqual(component, self.components_data[2])

    @mock.patch.object(ParentComponentsAsync, 'get_event_loop')
    @mock.patch.object(ParentComponentsAsync, 'get_component_and_links')
    def test_get_components_data(self, mock_get_component_and_links,
                                 mock_get_event_loop):
        mock_get_component_and_links.return_value = \
            self.links, self.components_data[3]
        mock_get_event_loop.return_value = self.components_data[:-1]
        self.assertEqual(
            self.container_components.get_components_data('OCI'),
            self.group_components_data
        )


class TestMapSourceImage(TestCase):
    def setUp(self):
        os.environ.setdefault(
                'DJANGO_SETTINGS_MODULE', 'openlcs.openlcs.settings')
        self.binary_nvr = 'dotnet-21-container-2.1-54'
        self.source_nvr = 'dotnet-21-container-source-2.1-54.3'
        self.context = {'config': {'KOJI_DOWNLOAD': settings.KOJI_DOWNLOAD,
                                   'KOJI_WEBSERVICE': settings.KOJI_WEBSERVICE,
                                   'KOJI_WEBURL': settings.KOJI_WEBURL
                                   },
                        }

    def test_get_latest_source_container_build(self):
        binary_nvr = self.binary_nvr
        connector = KojiConnector(self.context.get('config'))
        source_image = connector.get_latest_source_container_build(
                binary_nvr)
        self.assertEqual(source_image.get('nvr'), self.source_nvr)
