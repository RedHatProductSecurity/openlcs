import glob
import json
import os
import shutil
import socket
import tempfile
from http import HTTPStatus
from requests.exceptions import HTTPError

from checksumdir import dirhash
from commoncode.fileutils import delete
from workflow.patterns.controlflow import IF
from workflow.patterns.controlflow import IF_ELSE
from workflow.patterns.controlflow import WHILE
from packagedcode.rpm import RpmArchiveHandler
from packagedcode.pypi import PypiSdistArchiveHandler
from packagedcode.maven import parse as MavenPomXmlHandler

from openlcsd.celery import app
from openlcsd.flow.task_wrapper import WorkflowWrapperTask
from openlcs.libs.common import get_component_name_version_combination
from openlcs.libs.common import get_nvr_list_from_components
from openlcs.libs.common import remove_duplicates_from_list_by_key
from openlcs.libs.common import run_and_capture
from openlcs.libs.common import ExhaustibleIterator
from openlcs.libs.corgi import CorgiConnector
from openlcs.libs.driver import OpenlcsClient
from openlcs.libs.kojiconnector import KojiConnector
from openlcs.libs.logger import get_task_logger
from openlcs.libs.metadata import CargoMeta
from openlcs.libs.metadata import GolangMeta
from openlcs.libs.metadata import NpmMeta
from openlcs.libs.metadata import GemMeta
from openlcs.libs.parsers import sha256sum
from openlcs.libs.scanner import BaseScanner
from openlcs.libs.scanner import LicenseScanner
from openlcs.libs.scanner import CopyrightScanner
from openlcs.libs.sc_handler import SourceContainerHandler
from openlcs.libs.swh_tools import get_swhids_with_paths
from openlcs.libs.unpack import UnpackArchive
from openlcs.utils.common import DateEncoder
from openlcs.libs.encrypt_decrypt import encrypt_with_secret_key


def get_config(context, engine):
    """
    Get the hub configure information.

    @requires: 'task_id', id of the task. needed while initializing logger

    @feeds: `config`, dict, configurations obtained from Hub.
    @feeds: `client`, a OpenlcsClient instance, to communicate with Hub.
    @feeds: `tmp_root_dir`, destination dir where temporary source
                            will be placed.
    @feeds: `post_dir`, destination dir where temporary post/adhoc_post data
                        file will be placed.
    """
    config = {}

    # Get config data
    try:
        task_id = context.get('task_id')
        token = context.get('token')
        token_sk = context.get('token_sk')
        client = OpenlcsClient(task_id=task_id, token=token, token_sk=token_sk)
        resp = client.get('obtain_config')
        if resp.status_code == HTTPStatus.OK:
            config = resp.json()
    except RuntimeError as err:
        err_msg = f'Failed to get config data. Reason: {err}'
        engine.logger.error(err_msg)
        raise RuntimeError(err_msg) from None
    # One-time file based logger configuration for each task.
    logger_dir = config.get("LOGGER_DIR")
    engine.logger = get_task_logger(logger_dir, task_id)

    # Temporary package source tarball will be stored in a separate
    # directory under "SRC_ROOT_DIR".
    tmp_root_dir = config.get('TMP_ROOT_DIR')
    if not os.path.exists(tmp_root_dir):
        os.mkdir(tmp_root_dir)
    context['tmp_root_dir'] = tmp_root_dir

    post_dir = config.get('POST_DIR')
    if not os.path.exists(post_dir):
        os.mkdir(post_dir)
    context['post_dir'] = post_dir

    context['config'] = config
    context['client'] = client
    engine.logger.info("Worker {}".format(socket.gethostname()))


def get_build(context, engine):
    """
    Get build from brew/koji.

    @requires: `config`, configuration from hub server.
    @requires: `package_nvr`, `rpm_nvra`.
    @feeds: `build`, dictionary, including meta info with the build.
    @feeds: `build_type`, dict, with keys as build type names and values as
                type info corresponding to that type.
    """
    # Not get build when sync component form Corgi.
    provenance = context.get('provenance')
    if provenance and provenance == 'sync_corgi':
        component = context.get('component')
        component_type = component.get('type')
        context['build_type'] = {component_type: None}
        context['component_type'] = component_type
    else:
        config = context.get('config')
        rs_comp = context.get('rs_comp')
        if rs_comp:
            rs_type = rs_comp.get('type')
            if rs_type in config.get('RS_TYPES'):
                context['build_type'] = {rs_type: None}
                context['build'] = {
                    'name': rs_comp.get('name'),
                    'version': rs_comp.get('version'),
                    'release': rs_comp.get('release'),
                    'summary_license': '',
                    'arch': rs_comp.get('arch'),
                    'type': rs_type,
                }
        else:
            koji_connector = KojiConnector(config)
            build = koji_connector.get_build_extended(
                context.get('package_nvr'),
                context.get('rpm_nvra')
            )
            build_type = koji_connector.get_build_type(build)
            context['build_type'] = build_type
            context['build'] = build

        if context.get('component_type'):
            component_type = context.get('component_type')
        elif context.get('rs_comp'):
            component_type = context.get('rs_comp')['type']
        else:
            comp_type = list(context['build_type'].keys())[0]
            if comp_type == 'image':
                component_type = 'OCI'
            elif comp_type == 'module':
                component_type = 'RPMMOD'
            else:
                component_type = comp_type.upper()
        context['component_type'] = component_type


def filter_duplicate_import(context, engine):
    """
    Filter duplicate import.

    """
    url = 'check_duplicate_import'
    cli = context.get('client')
    component_type = context.get('component_type')
    build_data = context.get('build', {})
    if component := context.get('component'):
        data = {
            'name': component.get('name'),
            'version': component.get('version'),
            'release': component.get('release'),
            'type': component.get('type'),
            'parent': context.get('parent', ''),
            'arch': component.get('arch')
        }
    else:
        data = {
            'name': build_data.get('name', ''),
            'version': build_data.get('version', ''),
            'release': build_data.get('release', ''),
            'type': component_type,
            'parent': context.get('parent', ''),
            'arch': '' if component_type == 'RPMMOD' else build_data.get(
                'arch', 'src')
        }
    msg = f'Start to check duplicate import for {data}'
    engine.logger.info(msg)
    resp = cli.post(url, data=data)
    if resp.status_code == 200:
        if results := resp.json().get('results'):
            if obj_url := results.get('obj_url'):
                task_id = context.get('task_id')
                msg = f'Found duplicate import for task: ' \
                      f'{task_id}, obj_url: {obj_url}'
                engine.logger.warning(msg)
                context['duplicate_import'] = True
    engine.logger.info("Finished checking duplicate import.")


def get_source_container_build(context, engine):
    """
    Get source container build with brew/koji API.
    @requires: `config`, configuration from hub server.
    @requires: `build`, dictionary, including meta info with the build.
    @feeds: `build`, dictionary, including meta info with the build of
            source image.
    @feeds: `binary_build`, dict, the brew build corresponding to the
            binary nvr.
    @feeds: `build_type`, dict, with keys as build type names and values as
            type info corresponding to that build.
    """
    config = context.get('config')
    koji_connector = KojiConnector(config)
    build = context.get('build')
    sc_build = None
    package_nvr = context.get('package_nvr')
    # Use the build directly if the build is for source container.
    if package_nvr and 'container-source' in package_nvr:
        if koji_connector.is_source_container_build(build):
            sc_build = build
    # Get the source container build if the input is a binary container.
    elif package_nvr and 'container' in package_nvr:
        sc_build = koji_connector.get_latest_source_container_build(
            package_nvr)

    if sc_build:
        #  Add build id in the json.
        if "id" not in sc_build:
            sc_build["id"] = sc_build.get("build_id")
        # Get the binary build for the import source container nvr.
        if package_nvr == sc_build.get('nvr'):
            binary_nvr = koji_connector.get_binary_nvr(package_nvr)
            binary_build = koji_connector.get_build(binary_nvr)
        else:
            msg = 'Found source container build %s for %s in Brew/Koji'
            engine.logger.info(msg % (sc_build.get('nvr'), package_nvr))
            binary_build = context.get('build')
        context['binary_build'] = binary_build
        context['build'] = sc_build
        context['build_type'] = koji_connector.get_build_type(sc_build)

    else:
        err_msg = "This binary container has no mapping source container."
        engine.logger.error(err_msg)
        raise ValueError(err_msg) from None


def download_source_image(context, engine):
    """
    Download the container source image.
    With normalized parameters, returning an absolute path \
    to which the image is being downloaded.

    @requires: `config`, configuration from hub server.
                It's not always required.
    @requires: `client`, to communicate with hub server.
                It's not always required.
    @feeds: `tmp_src_filepath`, absolute path to the downloaded image.
    """
    tmp_dir = tempfile.mkdtemp(prefix='download_sc_',
                               dir=context.get('tmp_root_dir'))
    config = context.get('config')
    build = context.get('build')

    koji_connector = KojiConnector(config)
    arch = 'x86_64'
    # First, try to get the source from repository
    # Otherwise, get the source from the source container image
    repository = koji_connector.get_task_repository(build)
    if repository:
        engine.logger.info("Start getting source from registry......")
        koji_connector.get_source_from_registry(repository, tmp_dir)
    else:
        msg = "Start to download container source image build from Brew/Koji, "
        msg += "please wait for the task log update..."
        engine.logger.info(msg)
        koji_connector.download_container_image_archives(build, tmp_dir, arch)
    engine.logger.info('Done')
    tmp_src_filepath = os.path.join(tmp_dir, os.listdir(tmp_dir)[0])
    context['tmp_src_filepath'] = tmp_src_filepath


def download_package_archive(context, engine):
    """
    Download source of given build/archive.
    With normalized parameters, returning an absolute path \
    to which the archive is being downloaded.

    @requires: `config`, configuration from hub server.
    @requires: `client`, to communicate with hub server.
    @feeds: `tmp_src_filepath`, absolute path to the downloaded archive.
    @feeds: `tmp_pom_filepath`, absolute path to the pom file, None if
            not found. Note that this is available only for maven builds.
    """
    tmp_dir = tempfile.mkdtemp(
        prefix='download_', dir=context.get('tmp_root_dir'))
    config = context.get('config')
    koji_connector = KojiConnector(config)
    component = context.get('component')
    if build := context.get('build'):
        build_id = build.get('id')
    else:
        software_build = component.get('software_build') if component else None
        build_id = software_build.get('build_id') if software_build else None
    engine.logger.info('Start to download package source...')
    try:
        if build_id:
            koji_connector.download_build_source(int(build_id),
                                                 dest_dir=tmp_dir)
        else:
            # For remote source, we should use 'download_url' to download
            # pacakge archive
            if component and (download_url := component.get('download_url')):
                cmd = None
                tarball_extensions = [
                    '.tgz', '.tar.gz', '.zip', '.gem', '.crate'
                ]
                for extension in tarball_extensions:
                    if download_url.endswith(extension):
                        cmd = f'wget -q --show-progress {download_url}'
                        break
                comp_type = component.get('type')
                with_download = download_url.endswith('download')
                if cmd is None and comp_type == 'CARGO' and with_download:
                    ofile = component.get('nvr') + '.crate'
                    cmd = f'wget -O {ofile} -q --show-progress {download_url}'
                if cmd:
                    ret_code, err_msg = run_and_capture(cmd, tmp_dir)
                    if ret_code:
                        raise RuntimeError(err_msg)
                else:
                    err_msg = f"Currently, we don't support this URL: " \
                              f"{download_url}."
                    raise RuntimeError(err_msg)
            else:
                err_msg = "Download URL not exist."
                raise RuntimeError(err_msg)
    except RuntimeError as err:
        nvr = build.get('nvr') if build else component.get('nvr')
        err_msg = f'Failed to download source for {nvr}: {err}'
        engine.logger.error(err_msg)
        raise RuntimeError(err_msg) from None

    tmp_src_filepath = os.path.join(tmp_dir, os.listdir(tmp_dir)[0])
    context['tmp_src_filepath'] = tmp_src_filepath

    if (build_type := context.get('build_type')) and 'maven' in build_type:
        try:
            pom_path = koji_connector.get_pom_pathinfo(
                build_id=build.get('id'))
        except ValueError as e:
            context['tmp_pom_filepath'] = None
            engine.logger.warning("%s" % e)
        else:
            koji_connector.download_pom(pom_path, tmp_dir)
            pom_files = glob.glob("%s/*.pom" % tmp_dir)
            if pom_files:
                context['tmp_pom_filepath'] = pom_files[0]

    engine.logger.info('Finished downloading source.')


def is_metadata_component_source(src_filepath):
    # based on current approach, the metadata component source for an
    # image build will be placed in `src_root/metadata` directory
    return (os.path.isdir(src_filepath)
            and os.path.basename(src_filepath) == "metadata")


def download_component_source(context, engine):
    """
    Download the component src from brew. If the component's src was
    downloaded from source container, then no need to download source of the
    package archive from brew.
    @requires: `config`, configuration from hub server.
    @requires: `package_nvr`, nvr of the package.
    @requires: `src_dir`, source directory.
    @feeds: `tmp_src_filepath`, absolute path of component source tarball.
    """
    src_dir = context.get('src_dir')
    if not context.get('src_dir'):
        download_package_archive(context, engine)
    else:
        config = context.get('config')
        nvr = context.get('package_nvr')
        sc_handler = SourceContainerHandler(config)
        if 'rpm_dir' in src_dir:
            source_path = sc_handler.get_source_of_srpm_component(
                src_dir, nvr)
        # metadata(miscellaneous) component source from within image
        elif is_metadata_component_source(src_dir):
            source_path = src_dir
        elif 'rs_dir' in src_dir:
            component = context.get('rs_comp')
            source_path = sc_handler.get_source_of_remote_source_components(
                src_dir, component)
        else:
            source_path = ""

        if source_path:
            context['tmp_src_filepath'] = source_path
        else:
            err_msg = "Failed to get component source path in container."
            engine.logger.error(err_msg)
            raise RuntimeError(err_msg) from None


def get_source_metadata(context, engine):
    """
    Get package metadata(upstream url, declared license) after source archive
    is downloaded.

    @requires: 'tmp_src_filepath' for rpm, 'tmp_pom_filepath' for maven build.
    @feeds: 'project_url' - string, package upstream source URL.
    @feeds: 'declared_license' - string, package declared license.
    """

    engine.logger.info("Start to get source package metadata...")
    src_filepath = context.get('tmp_src_filepath')
    nvr = context.get('package_nvr')
    if is_metadata_component_source(src_filepath):
        source_name = f"{nvr}-metadata"
        source_checksum = dirhash(src_filepath, "sha256")
    else:
        source_name = os.path.basename(src_filepath)
        source_checksum = sha256sum(src_filepath)
    build_type = context.get('build_type')
    package = None
    pom_filepath = context.get('tmp_pom_filepath', None)
    try:
        if 'rpm' in build_type or 'RPM' in build_type:
            packages = RpmArchiveHandler.parse(src_filepath)
            package = next(packages)
        elif 'PYPI' in build_type:
            packages = PypiSdistArchiveHandler.parse(src_filepath)
            package = next(packages)
        elif 'NPM' in build_type or 'YARN' in build_type:
            retval = NpmMeta(src_filepath).parse_metadata()
            if isinstance(retval, str):
                engine.logger.warning(f"Failed to get metadata: {retval}")
                package = None
            else:
                package = retval
        elif 'GOLANG' in build_type:
            retval = GolangMeta(src_filepath).parse_metadata()
            if isinstance(retval, str):
                engine.logger.warning(f"Failed to get metadata: {retval}")
                package = None
            else:
                package = retval
        elif 'CARGO' in build_type:
            retval = CargoMeta(src_filepath).parse_metadata()
            if isinstance(retval, str):
                engine.logger.warning(f"Failed to get metadata: {retval}")
                package = None
            else:
                package = retval
        elif 'GEM' in build_type:
            package = GemMeta(src_filepath).parse_metadata()
        elif pom_filepath is not None:
            packages = MavenPomXmlHandler.parse(pom_filepath)
            package = next(packages)
    except Exception as e:
        engine.logger.warning(str(e))

    if package is not None:
        # Package below urls which could be referenced as project url,
        # e.g.,
        # homepage_url: http://cxf.apache.org
        # repository_homepage_url: https://crates.io/crates/zvariant_derive
        # code_view_url: https://gitbox.apache.org/repos/asf?p=cxf.git;a=summary    # noqa
        # homepage_url --> repository_homepage_url --> code_view_url
        urls = ['homepage_url', 'repository_homepage_url', 'code_view_url']
        for url in urls:
            if hasattr(package, url):
                context['project_url'] = getattr(package, url)
                break
        context['declared_license'] = package.declared_license
    else:
        context['project_url'] = ''
        context['declared_license'] = ''

    source_info = {
        'product_release': context.get('product_release'),
        "source": {
            "checksum": source_checksum,
            "name": source_name,
            "url": context.get("project_url"),
            "archive_type": list(build_type.keys())[0]
        },

    }
    if build := context.get('build'):
        source_info.update(
            {"component": {
                "name": build.get('name'),
                "version": build.get('version'),
                "release": build.get('release'),
                "arch": 'src',
                "type": context.get('component_type'),
                "summary_license": context.get("declared_license", ""),
                "is_source": True
            }}
        )
    elif component := context.get('component'):
        # Use a shallow copy so we won't polluate the original component.
        component_info = component.copy()
        declared_license = component_info.pop("declared_license", "")
        component_info["summary_license"] = declared_license
        component_info["is_source"] = True
        component_info["from_corgi"] = True
        source_info.update(
            {"component": component_info}
        )
    else:
        msg = "Failed to get component information."
        engine.logger.error(msg)
        raise RuntimeError(msg)
    context['source_info'] = source_info
    if source_name == f"{nvr}-metadata":
        context['source_info']['source']['archive_type'] = 'tar'

    engine.logger.info("Done")


def check_source_status(context, engine):
    """
    Check if the source exist in database, if existed, get the scan_flag

    @requires: `source_info`, dict, source information.
    @feeds: `source_api_url`, string, the restful API url of the source.
    @feeds: `source_scan_flag`, string, source scan license and copyright flag.
    """
    checksum = context['source_info']['source']['checksum']
    try:
        response = get_data_using_post(context.get('client'),
                                       '/check_source_status/',
                                       {"checksum": checksum})
    except RuntimeError as err:
        engine.logger.error(err)
        raise RuntimeError(err) from None
    context['source_api_url'] = response.get('source_api_url')
    context['source_scan_flag'] = response.get('source_scan_flag')


def get_scanner(context, engine):
    # 'scanner' param could be added as an input when multiple scanners.
    # Default is scancode.
    config = context.get('config')
    base_scanner = BaseScanner(config=config)
    base_scanner.get_scanner_version()
    context['detector'] = base_scanner.detector


def check_source_scan_status(context, engine):
    """
    Check if the source have been scanned.
    If the source not exist, according scan tag to check if it needs to scan.
    If the source exist, according scan tag and currently scan status to
    check if it needs to scan.

    @requires: `source_api_url`, string, the restful API url of the source.
    @requires: `config`, configuration from hub server.
    @feeds: `license_scan_req`, bool, if the source need scan license,
             it will be True.
    @feeds: `copyright_scan_req`,  bool, if the source need scan copyright,
             it will be True.
    @feeds: `source_scanned`,  bool, if the source not need to scan,
             it will be True.
    """
    check_source_status(context, engine)
    license_scan_req = False
    copyright_scan_req = False
    source_scanned = False
    license_scan_tag = context.get('license_scan')
    copyright_scan_tag = context.get('copyright_scan')

    # If the source exist, check if it needs to scan.
    if context.get('source_api_url'):
        detector = context.get('detector')
        license_flag = "license(" + detector + ")"
        copyright_flag = "copyright(" + detector + ")"
        source_scan_flag = context['source_scan_flag']
        if source_scan_flag:
            if license_scan_tag and license_flag not in source_scan_flag:
                license_scan_req = True
            elif copyright_scan_tag and copyright_flag not in source_scan_flag:
                copyright_scan_req = True
        else:
            license_scan_req = True if license_scan_tag else False
            copyright_scan_req = True if copyright_scan_tag else False

        # If source exist, and have been scanned or not need to scan
        if not license_scan_req and not copyright_scan_req:
            source_scanned = True
            msg = f"Found a source" \
                  f"({context['source_info']['source']['name']}) " \
                  f"meeting the requirements already imported. " \
                  f"The REST API link is: {context['source_api_url']}"
            engine.logger.info(msg)
    # If the source not exist, check if it needs to scan.
    else:
        license_scan_req = True if license_scan_tag else False
        copyright_scan_req = True if copyright_scan_tag else False
    context['license_scan_req'] = license_scan_req
    context['copyright_scan_req'] = copyright_scan_req
    context['source_scanned'] = source_scanned


def prepare_dest_dir(context, engine):
    """
    Create destination directory based on config.
    For builds from brew/koji, if destination dir already exists,
    remove it recursively and create new one.

    @requires: `config`, configuration from hub server.
    @requires: `build`, meta info with the build.
    @feeds: `src_dest_dir`, destination dir where source will be placed.
    """
    config = context.get('config')
    build = context.get('build')
    release = context.get('product_release')
    parent = context.get('parent')
    component_type = context.get('component_type')
    rs_types = config.get('RS_TYPES')
    engine.logger.info('Start to prepare destination directory...')
    # TODO: Currently we don't store product and release data, so the
    # release should be added manually if release is needed in import.
    src_root = config.get('SRC_ROOT_DIR')
    if src_root:
        if release:
            dir_name = release.get('short_name') if isinstance(release, dict) \
                    else release
        else:
            dir_name = config.get('ORPHAN_CATEGORY')
        dest_root = os.path.join(src_root, dir_name)
    else:
        dest_root = context.get('tmp_root_dir')
    nvr = build.get('nvr') if build else context.get('component').get('nvr')
    if parent:
        dest_root = os.path.join(dest_root, parent)
    if component_type == 'RPM':
        src_dir = os.path.join(dest_root, nvr)
    elif component_type in rs_types:
        rs_comp = context.get('rs_comp')
        component = context.get('component')
        rs_comp = rs_comp if rs_comp else component
        rs_nv = get_component_name_version_combination(rs_comp)
        src_dir = os.path.join(dest_root, rs_nv)
    elif component_type == 'OCI' and parent:
        metadata_dir = nvr + '-metadata'
        src_dir = os.path.join(dest_root, metadata_dir)
    else:
        src_dir = tempfile.mkdtemp(
            prefix='src_', dir=context.get('tmp_root_dir'))
    if os.path.exists(src_dir):
        delete(src_dir)
    try:
        os.makedirs(src_dir)
    except OSError as err:
        msg = f"Failed to create directory {src_dir}: {err}"
        engine.logger.error(msg)
        raise RuntimeError(msg) from None
    engine.logger.info('Finished preparing destination directory.')
    context['src_dest_dir'] = src_dir


def extract_source(context, engine):
    """
    Extract source to destination directory if specified, /tmp otherwise.

    @requires(optional): `src_dest_dir`, destination source directory.
    @requires: `tmp_src_filepath`: absolute path to the archive.
    @feeds: `archive_mime_type`: mimetype of archive.
    """
    src_dest_dir = context.get('src_dest_dir', '/tmp')
    # FIXME: exception handling
    tmp_src_filepath = context.get('tmp_src_filepath', None)
    engine.logger.info('Start to extract source...')

    if is_metadata_component_source(tmp_src_filepath):
        mime_type = None
        shutil.copytree(tmp_src_filepath, src_dest_dir, dirs_exist_ok=True)
    else:
        ua = UnpackArchive(src_file=tmp_src_filepath, dest_dir=src_dest_dir)
        mime_type = ua._get_archive_type()
        ua.extract()
    engine.logger.info('Finished extracting source.')
    context['archive_mime_type'] = mime_type


def unpack_source(context, engine):
    """
    Recursively unpack sources of given build/archive.

    @requires: 'src_dest_dir', destination directory.
    @feeds: 'None', archives will be recursively unpacked upon success.
    """
    prepare_dest_dir(context, engine)
    extract_source(context, engine)

    config = context.get('config')
    src_dest_dir = context.get('src_dest_dir')
    engine.logger.info('Start to unpack source archives...')
    ua = UnpackArchive(config=config, dest_dir=src_dest_dir)
    unpack_errors = ua.unpack_archives()
    if unpack_errors:
        err_msg = "---- %s" % "\n".join(unpack_errors)
        engine.logger.warning(err_msg)
    engine.logger.info("Finished unpacking source.")


def unpack_container_source_archive(context, engine):
    """
    Uncompress sources of given build/archive.
    @requires: `config`, configuration from hub server.
    @requires: 'tmp_src_filepath', absolute path to the archive.
    @requires: 'src_dest_dir', destination directory.
    @feeds: 'misc_dir', directory to store misc files.
    @feeds: 'srpm_dir', directory to store source RPMs.
    @feeds: 'rs_dir', directory to store remote source
    """
    prepare_dest_dir(context, engine)
    config = context.get('config')
    tmp_src_filepath = context.get('tmp_src_filepath')
    src_dest_dir = context.get('src_dest_dir')

    # Unpack the source container image.
    sc_handler = SourceContainerHandler(config, tmp_src_filepath, src_dest_dir)
    engine.logger.info('Start to unpack source container files...')
    try:
        srpm_dir, rs_dir, misc_dir, errs = \
                sc_handler.unpack_source_container_image()
    except (ValueError, RuntimeError) as err:
        err_msg = "Failed to decompress file %s: %s" % (tmp_src_filepath, err)
        engine.logger.error(err_msg)
        raise RuntimeError(err_msg) from None
    if len(errs) > 0:
        engine.logger.error(errs)
    engine.logger.info('Finished unpacking the source files.')
    context['misc_dir'], context['srpm_dir'], context['rs_dir'] = \
        misc_dir, srpm_dir, rs_dir


def get_source_files_paths(source_dir):
    """
    Get all paths to these files in the source, except soft link.
    """
    path_list = []
    if source_dir:
        for root, _, files in os.walk(source_dir):
            for file in files:
                file_path = os.path.join(root, file)
                if not os.path.islink(file_path):
                    path_list.append(file_path)
    return path_list


def get_data_using_post(client, url, data):
    """
    Run the API command, and return the data.
    """
    resp = client.post(url, data)
    try:
        resp.raise_for_status()
    except HTTPError as err:
        raise RuntimeError(err) from None
    return resp.json()


def deduplicate_source(context, engine):
    """
    Exclude files that were already in db, and returns a subset of source
    directory with only files unseen before.

    Note: this requires to traverse the whole source directory, get
    each file hash and check file existence in db, thus could be
    resource intensive.

    @requires: `src_dest_dir`,the archive unpack directory.
    @feeds: `swhids`, swhid list for files in the source.
    @feeds: `paths`, path information list for files in the source.
    """
    engine.logger.info('Start to deduplicate source...')
    src_dest_dir = context.get("src_dest_dir")
    if src_dest_dir:
        path_list = get_source_files_paths(src_dest_dir)
        if path_list:
            path_swhid_list = get_swhids_with_paths(path_list)
            # Remove source root directory in path
            paths = [
                os.path.relpath(item[0], src_dest_dir)
                for item in path_swhid_list
            ]
            path_swhids = list(zip(*path_swhid_list))[1]
            rel_path_swhids = list(zip(paths, path_swhids))
            context['path_with_swhids'] = rel_path_swhids
            swhids = [path_swhid[1] for path_swhid in path_swhid_list]

            try:
                # Deduplicate files.
                data = {'swhids': swhids,
                        'detector': context.get('detector'),
                        'license_scan': context.get('license_scan'),
                        'copyright_scan': context.get('copyright_scan')}
                response = get_data_using_post(context.get('client'),
                                               '/check_duplicate_files/', data)
                duplicate_swhids = response.get('duplicate_swhids')
                if duplicate_swhids:
                    swhids = list(
                        set(swhids).difference(set(duplicate_swhids)))
                    for path, swhid in path_swhid_list:
                        if swhid in duplicate_swhids:
                            os.remove(path)
                else:
                    swhids = list(set(swhids))
                context['source_info']['swhids'] = swhids if swhids else []

                # All the paths need to be stored. because even if file exist,
                # that's not mean the path object exist.
                # They are many-one relationship.
                context['source_info']['paths'] = [{
                    "path": path,
                    "file": swhid
                } for (path, swhid) in rel_path_swhids]
            except RuntimeError as err:
                err_msg = f"Failed to check duplicate files. Reason: {err}"
                engine.logger.error(err_msg)
                raise RuntimeError(err_msg) from None
    else:
        err_msg = "Failed to find unpack source directory path."
        engine.logger.error(err_msg)
        raise RuntimeError(err_msg)
    engine.logger.info("Finished deduplicating source.")


def save_package_data(context, engine):
    """
    Equivalent of the former "post"/"post_adhoc", which sends/posts
    results to hub. But exclude scan result, they posted in other step.
    """
    url = 'packageimporttransaction'
    cli = context.pop('client')
    if component := context.get('component'):
        component_nvr = component.get('nvr')
    else:
        package_nvr = context.get('package_nvr')
        component_nvr = package_nvr if package_nvr else context.get('rs_comp')
    engine.logger.info(f"Start to send {component_nvr} data to hub for "
                       f"further processing...")
    # Post data file name instead of post context data
    fd, tmp_file_path = tempfile.mkstemp(prefix='send_package_',
                                         dir=context.get('post_dir'))
    with os.fdopen(fd, 'w') as destination:
        file_content = {
            'source_info': context.get("source_info"),
            'task_id': context.get('task_id')
        }
        json.dump(file_content, destination, cls=DateEncoder)
    resp = cli.post(url, data={"file_path": tmp_file_path}, timeout=420)
    context['client'] = cli
    try:
        # Raise it in case we made a bad request:
        # http://docs.python-requests.org/en/master/user/quickstart/#response-status-codes  # noqa
        resp.raise_for_status()
    except HTTPError:
        err_msg = f"Failed to save {component_nvr} data to db: {resp.text}"
        engine.logger.error(err_msg)
        raise RuntimeError(err_msg) from None
    finally:
        os.remove(tmp_file_path)
    engine.logger.info(f"Finished saving {component_nvr} data to database.")


def license_scan(context, engine):
    """
    Scan license under a given directory.

    @requires: `src_dest_dir`, source directory.
    @requires: `config`, configuration from hub.
    @feeds: `scan_result`, scan result updated with license scan data.
    """
    src_dir = context.get('src_dest_dir')
    config = context.get('config')
    # Scanner could be provided when multiple scanners supported in the future.
    engine.logger.info("Start to scan source licenses with Scancode...")
    scanner = LicenseScanner(
            config=config, src_dir=src_dir, logger=engine.logger)
    (detector, licenses, errors, has_exception) = scanner.scan()
    engine.logger.info("Done")
    scan_result = {
        "source_checksum": context.get("source_info").get("source").get(
            "checksum")}
    scan_result.update({
        "license_detector": detector,
        "license_scan": context.get('license_scan'),
        "path_with_swhids": context.get('path_with_swhids'),
        "licenses": {
            "data": licenses,
            "errors": errors,
            "has_exception": has_exception
        }
    })
    context['scan_result'] = scan_result


def copyright_scan(context, engine):
    """
    Scan copyright under a given directory.

    @requires: `src_dest_dir`, destination directory.
    @requires: `config`, configurations from Hub.
    @feeds: `copyrights`, raw copyrights findings.
    @feeds: `copyright_errors`, copyrights errors findings.
    @feeds: `copyright_exception`, exception during copyright scanning.
    """
    src_dir = context.get('src_dest_dir')
    config = context.get('config')
    engine.logger.info("Start to scan copyrights with Scancode...")
    scanner = CopyrightScanner(
            config=config, src_dir=src_dir, logger=engine.logger)
    (detector, copyrights, errors, has_exception) = scanner.scan()
    engine.logger.info("Done")
    scan_result = context.get('scan_result', {})
    if "source_checksum" not in scan_result:
        scan_result["source_checksum"] = context.get("source_info").get(
            "source").get("checksum")
    scan_result.update({
        "copyright_detector": detector,
        "copyright_scan": context.get('copyright_scan'),
        "path_with_swhids": context.get('path_with_swhids'),
        "copyrights": {
            "data": copyrights,
            "errors": errors,
            "has_exception": has_exception
        }
    })
    context['scan_result'] = scan_result


def save_scan_result(context, engine):
    """
    Equivalent of the former "post"/"post_adhoc", which sends/posts
    scan results to hub.
    """
    if 'scan_result' not in context:
        return
    url = 'savescanresult'
    cli = context.pop('client')
    if component := context.get('component'):
        component_nvr = component.get('nvr')
    else:
        package_nvr = context.get('package_nvr')
        component_nvr = package_nvr if package_nvr else context.get('rs_comp')
    engine.logger.info(f"Start to send {component_nvr} scan result to hub for "
                       f"further processing...")

    fd, tmp_file_path = tempfile.mkstemp(prefix='scan_result_',
                                         dir=context.get('post_dir'))
    try:
        with os.fdopen(fd, 'w') as destination:
            json.dump(context.get("scan_result"), destination, cls=DateEncoder)
    except Exception as e:
        err_msg = f"Failed to create scan result file: {e}"
        engine.logger.error(err_msg)
        raise RuntimeError(err_msg) from None
    resp = cli.post(url, data={"file_path": tmp_file_path})
    context['client'] = cli
    try:
        resp.raise_for_status()
    except HTTPError:
        err_msg = f"Failed to save scan result to database: {resp.text}"
        engine.logger.error(err_msg)
        raise RuntimeError(err_msg) from None
    finally:
        os.remove(tmp_file_path)
    engine.logger.info("Finished saving scan result to database.")


def sync_result_to_corgi(context, engine):
    component = context.get("component")
    if not component:
        err_msg = "Missing component in request!"
        engine.logger.error(err_msg)
        raise RuntimeError(err_msg)
    client = context['client']
    olcs_component_api_url = client.get_abs_url("components")
    component_uuid = component["uuid"]
    response = client.get("components", params={"uuid": component_uuid})
    response.raise_for_status()
    response = response.json()
    results = response["results"]
    # It's not clear to me how could results be empty without raising any
    # exceptions, the non-existent component makes it impossible to mark
    # the sync as failed.
    if not results:
        err_msg = (f"Failed to sync data to corgi, component "
                   f"{component_uuid} not found in OpenLCS.")
        engine.logger.error(err_msg)
        raise RuntimeError(err_msg)
    olcs_component = results[0]
    # Each component has one identical source.
    source = olcs_component["source"]
    if not source:
        # Component without source info means no scan is done.
        # FIXME: are there any other circumstances cause no source?
        engine.logger.warning(f"Component({component_uuid}) sync to corgi "
                              f"failed, no source found.")
        client.patch(
            f"components/{olcs_component['id']}",
            data={"sync_status": "sync_failed",
                  "sync_failure_reason": "scan_exception"})
        # This is non-blocking.
        return
    license_detections = source["license_detections"]
    copyright_detections = source["copyright_detections"]
    summary_license = olcs_component["summary_license"]
    component_data = {
        "uuid": component_uuid,
        "openlcs_scan_url": f"{olcs_component_api_url}{olcs_component['id']}",
        "openlcs_scan_version": source["scan_flag"],
        "license_declared": summary_license,
        # FIXME: Corgi by default concatenate list of licenses using "AND"
        "license_concluded": " AND ".join(license_detections),
        "copyright_text": ", ".join(copyright_detections),
    }
    connector = CorgiConnector()
    sync_fields = CorgiConnector.get_sync_fields(component)
    connector.sync_to_corgi(component_data, fields=sync_fields)
    engine.logger.info(f"Component({component_uuid}) synced to corgi.")
    client.patch(
        f"components/{olcs_component['id']}",
        data={"sync_status": "synced"})
    engine.logger.info(f"Component({component_uuid}) synced in OLCS.")


def get_source_components(context, engine):
    component = context.get("component")
    connector = CorgiConnector()
    gen = connector.get_source_component(component)
    components, missings = CorgiConnector.source_component_to_list(gen)
    if missings:
        context['components_missing'] = missings
        msg = f'Failed to sync these component(s) data from Corgi: ' \
              f'{missings}'
        engine.logger.warning(msg)
    context["components"] = components


def get_container_components(context, engine):
    """
    Get all component in the source container.
    """
    engine.logger.info('Start to get container components data...')
    # Collect container components from Corgi
    components = get_components_product_from_corgi(context, engine)
    # If we cannot get components from Corgi, parse them from source container
    if not components:
        components = get_components_from_source_container(
            context, engine)
    context['components'] = components
    engine.logger.info("Finished getting container components data.")


def get_components_product_from_corgi(context, engine):
    """
    Get components information from Corgi.
    @requires: `package_nvr`, string, the container nvr.
    @feeds: `components`, list of dictionary,
             components information of the container.
    """
    cc = CorgiConnector()
    nvr = context.get('build').get('nvr')
    return cc.get_components_data(nvr, "OCI")


def get_remote_source_components(context, engine):
    """
    Get remote source components in source container
    @requires: `config`, configurations from Hub.
    @requires: `binary_build`, brew build for the binary NVR.
    @returns: `rs_components`, remote source components in source container.
    """
    config = context.get('config')
    koji_connector = KojiConnector(config)
    engine.logger.info('Start to get remote source components...')
    try:
        rs_components = koji_connector.get_remote_source_components(
            context.get('binary_build'))
    except (RuntimeError, ValueError) as err:
        err_msg = f"Failed to get remote source components. Reason: {err}"
        engine.logger.error(err_msg)
        raise RuntimeError(err_msg) from None
    engine.logger.info('Finished getting remote source components.')
    return rs_components


def get_components_from_source_container(context, engine):
    """
    Get components in the source container.
    @requires: `config`, configurations from Hub.
    @requires: `package_nvr`, nvr of the container.
    @requires: `srpm_dir`, directory that store source RPMs.
    @returns: `components`, components found in the container.
    """
    config = context.get('config')
    sc_nvr = context.get('package_nvr')

    # Get components from the source container itself.
    srpm_dir = context.get('srpm_dir')
    sc_handler = SourceContainerHandler(config)
    components = sc_handler.get_container_components(srpm_dir, sc_nvr)

    # Get remote source components from its binary container.
    # There may be inconsistency between components listed in the remote
    # source json files and those collected from source container, OLCS-287.
    components.update(get_remote_source_components(context, engine))
    return components


def get_container_remote_source(context, engine):
    """
    Get remote source in container.
    @requires: `config`, configurations from Hub.
    @requires: `src_dest_dir`, destination source directory.
    @requires: `components`, components found in the container.
    @feeds: `missing_components`, components not found in the container,
            if there is any.
    @requires: `rs_dir`, directory that store remote source after collate.
    """
    config = context.get('config')
    rs_types = config.get('RS_TYPES')
    components = context.get('components')

    if any([True for rs_type in rs_types if rs_type in components.keys()]):
        engine.logger.info('Start to get remote source in source container...')
        rs_dir = context.get('rs_dir')
        src_dest_dir = os.path.dirname(rs_dir)
        sc_handler = SourceContainerHandler(config, dest_dir=src_dest_dir)
        rs_components = []
        for comp_type in rs_types:
            type_components = components.get(comp_type)
            if type_components:
                rs_components.extend(type_components)
        missing_components, missing_components_errors = \
            sc_handler.get_container_remote_source(rs_components)
        if missing_components:
            engine.logger.error("\n".join(missing_components_errors))
            context['missing_components'] = missing_components

        # Redefine the 'rs_dir' after collate remote source.
        context['rs_dir'] = os.path.join(context.get('src_dest_dir'), 'rs_dir')
        msg = "Finished getting remote source in source container."
        engine.logger.info(msg)


def save_components(context, engine):
    """
    Send container/module components to hub, then store the components.
    """
    package_nvr = context.get('package_nvr')
    component_type = context.get('component_type')
    cli = context.pop('client')
    url = 'savecomponents'
    data = {
        'components': context.get('components'),
        'product_release': context.get('product_release'),
        'component_type': component_type
    }
    msg = f'Start to save components in {component_type} {package_nvr}...'
    engine.logger.info(msg)
    fd, tmp_file_path = tempfile.mkstemp(
        prefix='save_components_', dir=context.get('post_dir'))
    with os.fdopen(fd, 'w') as destination:
        json.dump(data, destination, cls=DateEncoder)
    resp = cli.post(url, data={"file_path": tmp_file_path})
    context['client'] = cli
    try:
        resp.raise_for_status()
    except HTTPError:
        err_msg = f"Failed to save {component_type} components to " \
                  f"database: {resp.text}"
        engine.logger.error(err_msg)
        raise RuntimeError(err_msg) from None
    finally:
        os.remove(tmp_file_path)
    engine.logger.info(f'Finished saving {component_type} components.')


def get_module_components_from_corgi(context, engine):
    """
    Get module components from corgi
    """
    engine.logger.info("Start to get module components data...")
    mc = CorgiConnector()
    nvr = context.get("package_nvr")
    context['components'] = mc.get_components_data(nvr, 'RPMMOD')
    engine.logger.info("Finished getting module components data.")


def get_module_components_from_brew(context, engine):
    """
    Get module components from brew.
    @requires: `config`, configurations from Hub.
    @requires: 'module_nvr', module build nvr
    @returns: 'components', module and module child components
    """
    config = context.get('config')
    module_nvr = context.get('package_nvr')
    engine.logger.info("Start to get module components data...")
    koji_connector = KojiConnector(config)
    context['components'] = koji_connector.get_module_components(module_nvr)
    engine.logger.info("Finished getting module components data.")


def fork_specified_type_imports(
        context, engine, nvr_list, comp_type, src_dir=None):
    """
    In a source container, it has different type of component. The different
    components have different src dir. This function will be defined the post
    data for the source container srpm components' tasks. It could also be
    same with rhel module srpm components except the src dir.
    """
    cli = context.get('client')
    url = '/sources/import/'
    # Fork srpm tasks for module that has no src_dir param
    data = {
        'parent': context.get('package_nvr'),
        'component_type': comp_type,
        'package_nvrs': nvr_list,
        'license_scan': context.get('license_scan'),
        'copyright_scan': context.get('copyright_scan'),
        'parent_task_id': context.get('task_id'),
        'token': encrypt_with_secret_key(
            cli.headers['Authorization'].split()[-1],
            context['config']['TOKEN_SECRET_KEY']
        ),
        'token_sk': context['config']['TOKEN_SECRET_KEY'],
        'priority': context['priority']
    }
    # Fork srpm tasks for source container that downloaded src in src_dir
    if src_dir:
        data.update({'src_dir': src_dir})
    msg = 'Start to fork imports for {} components...'.format(len(nvr_list))
    engine.logger.info(msg)
    nvrs = "\n\t" + "\n\t".join(nvr_list)
    resp = cli.post(url, data=data)
    try:
        # Raise it in case we made a bad request:
        # http://docs.python-requests.org/en/master/user/quickstart/#response-status-codes  # noqa
        resp.raise_for_status()
    except HTTPError:
        err_msg = f'-- Failed to fork import tasks for components: {nvrs}. ' \
                  f'Reason: {resp.text}'
        engine.logger.error(err_msg)
        raise RuntimeError(err_msg) from None
    msg = f'-- Forked import tasks for components: {nvrs}'
    engine.logger.info(msg)
    engine.logger.info('Done')


def fork_remote_source_components_imports(
        context, engine, rs_comps, src_dir=None):
    """
    In a source container, it has different type of component. The different
    components have different src_dir. This function will be defined the post
    data for the different remote source component.
    """
    cli = context.get('client')
    url = '/sources/import/'
    data = {
        'parent': context.get('package_nvr'),
        'rs_comps': rs_comps,
        'license_scan': context.get('license_scan'),
        'copyright_scan': context.get('copyright_scan'),
        'parent_task_id': context.get('task_id'),
        'token': encrypt_with_secret_key(
            cli.headers['Authorization'].split()[-1],
            context['config']['TOKEN_SECRET_KEY']
        ),
        'token_sk': context['config']['TOKEN_SECRET_KEY'],
        'priority': context['priority']
    }
    # Fork remote source tasks for source container that
    # downloaded src in src_dir
    if src_dir:
        data.update({'src_dir': src_dir})
    msg = 'Start to fork imports for {} components...'.format(len(rs_comps))
    engine.logger.info(msg)
    components_string = ""
    for rs_comp in rs_comps:
        components_string += "\n\t" + 'name(%s) version(%s) type(%s)' % (
            rs_comp.get('name'), rs_comp.get('version'), rs_comp.get('type'))
    resp = cli.post(url, data=data)
    try:
        # Raise it in case we made a bad request:
        # http://docs.python-requests.org/en/master/user/quickstart/#response-status-codes  # noqa
        resp.raise_for_status()
    except HTTPError:
        err_msg = f'-- Failed to fork import tasks for components: ' \
                  f'{components_string}. Reason: {resp.text}'
        engine.logger.error(err_msg)
        raise RuntimeError(err_msg) from None

    msg = f'-- Forked import tasks for components: {components_string}'
    engine.logger.info(msg)
    engine.logger.info('Done')


def fork_components_imports(context, engine, parent, components):
    """
    Fork tasks for components import
    """
    cli = context.get('client')
    url = '/sources/import/'
    data = {
        'components': components,
        'license_scan': context.get('license_scan', True),
        'copyright_scan': context.get('copyright_scan', True),
        'parent_task_id': context.get('task_id'),
        'token': encrypt_with_secret_key(
            cli.headers['Authorization'].split()[-1],
            context['config']['TOKEN_SECRET_KEY']
        ),
        'token_sk': context['config']['TOKEN_SECRET_KEY'],
        'provenance': context.get('provenance'),
        'priority': context['priority']
    }

    source_components = context.get("source_components")
    if source_components is not None:
        data["subscription_id"] = source_components["subscription_id"]

    if parent:
        data['parent'] = parent
    msg = 'Start to fork imports for {} components...'.format(len(components))
    engine.logger.info(msg)
    components_string = "\n\t" + "\n\t".join([component.get('nvr')
                                              for component in components])
    resp = cli.post(url, data=data)
    try:
        # Raise it in case we made a bad request:
        # http://docs.python-requests.org/en/master/user/quickstart/#response-status-codes  # noqa
        resp.raise_for_status()
    except HTTPError:
        err_msg = f'-- Failed to fork import tasks for components: ' \
                  f'{components_string}. Reason: {resp.text}'
        engine.logger.error(err_msg)
        raise RuntimeError(err_msg) from None

    msg = f'-- Forked import tasks for components: {components_string}'
    engine.logger.info(msg)
    engine.logger.info('Done')


def fork_imports(context, engine):
    """
    Fork components tasks
    """
    components = context.get('components')
    if context.get('provenance') == 'sync_corgi':
        parent = context.get('component').get('uuid')
        fork_components_imports(context, engine, parent, components)
    else:
        srpm_nvr_list = get_nvr_list_from_components(components, 'RPM')
        # Fork rpm tasks for module or container
        if srpm_nvr_list:
            fork_specified_type_imports(
                context, engine, srpm_nvr_list, 'RPM', context.get('srpm_dir'))

        # Fork container-component tasks with the misc metadata files.
        if components.get('OCI'):
            fork_specified_type_imports(
                context, engine, [context.get('package_nvr')],
                'OCI', context.get('misc_dir'))

        # Fork remote source component tasks.
        config = context.get('config')
        rs_comps = []
        for comp_type in config.get('RS_TYPES'):
            comps = components.get(comp_type)
            if comps:
                rs_comps.extend(comps)
        missing_components = context.get('missing_components')
        if missing_components:
            rs_comps = [rs_comp for rs_comp in rs_comps
                        if rs_comp not in missing_components]
        if rs_comps:
            fork_remote_source_components_imports(
                context, engine, rs_comps, context.get('rs_dir'))


flow_default = [
    get_config,
    get_build,
    filter_duplicate_import,
    # Whether to skip the following steps according to `duplicate_import` flag
    IF(
        lambda o, e: not o.get('duplicate_import'),
        [
            # Different workflows could be used for different build types
            IF_ELSE(
                lambda o, e: o.get('provenance') == 'sync_corgi'
                             and ('OCI' in o.get('build_type') or 'RPMMOD' in o.get('build_type')),  # noqa
                # Work flow for sync with Corgi OCI/RPMMOD component
                [
                    get_source_components,
                    fork_imports,
                ],
                [
                    IF_ELSE(
                        lambda o, e: 'image' in o.get('build_type') and not o.get('parent'),  # noqa
                        # Work flow for import container build,
                        # but not for container metadata
                        [
                            get_source_container_build,
                            download_source_image,
                            unpack_container_source_archive,
                            get_container_components,
                            save_components,
                            get_container_remote_source,
                            fork_imports,
                        ],
                        [
                            IF_ELSE(
                                lambda o, e: 'module' in o.get('build_type'),
                                # Work flow for import module build
                                [
                                    get_module_components_from_brew,
                                    save_components,
                                    fork_imports,
                                ],
                                # Work flow for scan component source
                                [
                                    download_component_source,
                                    get_source_metadata,
                                    get_scanner,
                                    check_source_scan_status,
                                    IF(
                                        lambda o, e: not o.get("source_scanned"), # noqa
                                        [
                                            unpack_source,
                                            deduplicate_source,
                                            save_package_data,
                                            IF(
                                                lambda o, e: o.get('license_scan_req'), # noqa
                                                license_scan,
                                            ),
                                            IF(
                                                lambda o, e: o.get('copyright_scan_req'), # noqa
                                                copyright_scan,
                                            ),
                                            save_scan_result,
                                        ],
                                    ),
                                    IF(
                                        lambda o, e: o.get('provenance') == 'sync_corgi', # noqa
                                        sync_result_to_corgi,
                                    )
                                ]
                            )
                        ]
                    )
                ]
            )
        ]
    )
]

flow_retry = [
    get_config,
    IF(
        lambda o, e: o.get('license_scan'),
        license_scan,
    ),
    IF(
        lambda o, e: o.get('copyright_scan'),
        copyright_scan,
    ),
    save_scan_result,
]


def get_active_subscriptions(context, engine):
    """
    Returns list of active subscriptions
    @requires: client
    @feeds: subscriptions: list of subscriptions
    """
    subscriptions = list()
    client = context['client']
    # Only sync active subscriptions by default.
    query_params = {"active": "true"}
    for subscription in client.get_paginated_data(
            "subscriptions", query_params):
        context["subscription"] = subscription
        engine.logger.info(f"Collect components for {subscription['name']}")
        app.send_task("flow.tasks.flow_collect_components_for_subscription",
                      [{"subscription": subscription,
                        'provenance': 'sync_corgi'}])
        subscriptions.append(subscription)
    engine.logger.info(f"Collected {len(subscriptions)} subscriptions!")


def populate_source_components(context, engine):
    """Populate "source_components" by consuming from generator on demand,
    flow will be stopped in case generator is exhausted.

    @requires: components_generator
    @feeds: source_components
    """
    # Data returned is consumed one at a time here.
    components_generator = context.get("components_generator")
    try:
        source_components = next(components_generator)
    except StopIteration:
        # Stop the flow since all chunks are consumed.
        engine.stop()
    else:
        context["source_components"] = source_components


def collect_components(subscription):
    """
    Accept an active subscription, and yield collected components.

    Yield data follows below form:
    {
        "subscription_id": Integer, # id of the subscription model instance
        "sources": List(dict),      # List of the component data dictionary
        "missings": List(str)       # component link or purl
    }
    """
    connector = CorgiConnector()

    yield from connector.collect_components_from_subscription(subscription)


def populate_components_generator(context, engine):
    subscription = context.get("subscription", [])
    components = collect_components(subscription)
    context["components_generator"] = ExhaustibleIterator(components)


def populate_subscription_purls(context, engine):
    """
    Update component purls for subscriptions.

    @requires: source_components
    @requires: client
    @feeds: None
    """
    source_components = context["source_components"]
    subscription_id = source_components["subscription_id"]
    missings = list(set(source_components["missings"]))
    if missings:
        msg = f'Failed to sync these component(s) data from Corgi: ' \
              f'{missings}'
        engine.logger.warning(msg)
    sources = source_components["sources"]
    subscription_purl_set = set()
    source_purl_set = set()
    for component in sources:
        if component["type"] in ["OCI", "RPMMOD"]:
            provides = component.get("provides", [])
            # Store component provides purls.
            subscription_purl_set.update([p["purl"] for p in provides])
            # Store source component purls.
            olcs_sources = component.get("olcs_sources", [])
            source_purl_set.update([p["purl"] for p in olcs_sources])
        else:
            subscription_purl_set.add(component["purl"])
            source_purl_set.add(component["purl"])
    client = context["client"]
    resp = client.patch(
        f"subscriptions/{subscription_id}",
        data={
            "component_purls": list(subscription_purl_set),
            "missing_components": missings,
            "source_purls": list(source_purl_set)
        }
    )
    if resp.status_code != HTTPStatus.OK:
        err_msg = f'Failed to populate subscription purls: {resp.json()}'
        engine.logger.error(err_msg)
        raise RuntimeError(err_msg) from None
    engine.logger.debug(
        f"Populated purls for subscription {subscription_id}")


def translate_components(context, engine):
    """
    Accept list of raw components, translate into OLCS-recognizable inputs.
    """
    corgi_sources = []
    flat_components = []
    source_components = context["source_components"]
    sources = source_components.get('sources')
    for source in sources:
        if source.get('type') in ['OCI', 'RPMMOD']:
            olcs_sources = source.pop('olcs_sources')
            corgi_source = {'parent': source, 'components': olcs_sources}
            corgi_sources.append(corgi_source)
        else:
            flat_components.append(source)
    if flat_components:
        flat_components = remove_duplicates_from_list_by_key(
            flat_components, 'uuid')
        corgi_sources.append({'parent': {}, 'components': flat_components})
    context['corgi_sources'] = corgi_sources


def trigger_corgi_components_imports(context, engine):
    """
    Trigger fork tasks directly using Corgi source.
    """
    # set corgi source forked task medium priority
    engine.logger.info("Start to trigger Corgi component import.")
    context['priority'] = "medium"
    corgi_sources = context.get('corgi_sources')
    for corgi_source in corgi_sources:
        if parent := corgi_source.get('parent'):
            parent_uuid = parent.get('uuid')
        else:
            parent_uuid = None
        # Only fork for components without an openlcs_scan_url
        components = corgi_source.get('components')
        scan_components = []
        for comp in components:
            if comp.get('openlcs_scan_url'):
                continue
            scan_components.append(comp)
        if scan_components:
            fork_components_imports(
                    context, engine, parent_uuid, scan_components)
            scan_purls = [c['purl'] for c in scan_components]
            engine.logger.info(f"Forked imports for: {', '.join(scan_purls)}")
        else:
            engine.logger.info("The collected components have been scanned.")
    engine.logger.info("Done.")


# sub-flow of `flow_get_corgi_components`
process_collected_components = [
    populate_source_components,
    populate_subscription_purls,
    translate_components,
    trigger_corgi_components_imports
]


flow_collect_components_for_subscription = [
    get_config,
    populate_components_generator,
    WHILE(
        lambda o, e: o.get("components_generator").is_active,
        process_collected_components
    )
]


flow_get_active_subscriptions = [
    get_config,
    get_active_subscriptions
]


def register_task_flow(name, flow, **kwargs):
    @app.task(name=name, bind=True, base=WorkflowWrapperTask, **kwargs)
    def task(self, *args):
        # Note that the imports that this function requires must be done
        # inside since our code will not be running in the global context.
        from openlcsd.flow.core import OpenlcsWorkflowEngine

        wfe = OpenlcsWorkflowEngine()
        wfe.setWorkflow(flow)
        for arg in args:
            arg.setdefault('task_id', self.request.id)
        wfe.process(list(args))

    return task


register_task_flow('flow.tasks.flow_default', flow_default)
register_task_flow('flow.tasks.flow_retry', flow_retry)
register_task_flow('flow.tasks.flow_get_active_subscriptions',
                   flow_get_active_subscriptions)
register_task_flow('flow.tasks.flow_collect_components_for_subscription',
                   flow_collect_components_for_subscription)
