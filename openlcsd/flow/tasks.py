import glob
import json
import os
import shutil
import socket
import tempfile
from requests.exceptions import HTTPError

from workflow.patterns.controlflow import IF
from workflow.patterns.controlflow import IF_ELSE
from packagedcode.rpm import parse as rpm_parse
from packagedcode.maven import parse as maven_parse

from openlcsd.celery import app
from openlcsd.flow.task_wrapper import WorkflowWrapperTask
from openlcs.libs.common import get_nvr_list_from_components
from openlcs.libs.corgi_handler import ParentComponentsAsync
from openlcs.libs.download import KojiBuild
from openlcs.libs.driver import OpenlcsClient
from openlcs.libs.kojiconnector import KojiConnector
from openlcs.libs.logger import get_task_logger
from openlcs.libs.parsers import sha256sum
from openlcs.libs.scanner import LicenseScanner
from openlcs.libs.scanner import CopyrightScanner
from openlcs.libs.sc_handler import SourceContainerHandler
from openlcs.libs.swh_tools import get_swhids_with_paths
from openlcs.libs.unpack import UnpackArchive
from openlcs.utils.common import DateEncoder


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
        client = OpenlcsClient(task_id=task_id)
        resp = client.get('obtain_config')
        if resp.status_code == 200:
            config = resp.json()
    except RuntimeError as err:
        err_msg = f'Failed to get config data. Reason: {err}'
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
    @requires: `package_nvr`, `brew_tag`, `package_name`.
    @feeds: `build`, dictionary, including meta info with the build.
    @feeds: `build_type`, dict, with keys as build type names and values as
                type info corresponding to that type.
    """
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
        koji_build = KojiBuild(config)
        build = koji_build.get_build(
            context.get('package_nvr'),
            context.get('brew_tag'),
            context.get('package_name'),
            context.get('rpm_nvra'),
        )
        build_type = koji_build.get_build_type(build)
        context['build_type'] = build_type
        context['build'] = build

    # For forked source RPM task in container.
    if context.get('component_type'):
        comp_type = context.get('component_type')
    # For forked remote source task in container, and source RPM import
    elif context.get('rs_comp'):
        comp_type = context.get('rs_comp')['type']
    else:
        build_type = context.get('build_type')
        comp_type = "SRPM" if build_type == 'rpm' else build_type
    context['comp_type'] = comp_type


def is_source_container_build(context, build):
    """
    Check whether the build is a source container build.
    @requires: `build`, dictionary, the build got via API.
    @feeds: True, False
    """
    config = context.get('config')
    koji_connector = KojiConnector(config)
    container_type = koji_connector.get_osbs_build_kind(build)
    return container_type == 'source_container_build'


def get_source_container_build(context, engine):
    """
    Get Source container build with brew/koji API.
    @requires: `config`, configuration from hub server.
    @requires: `build`, dictionary, including meta info with the build.
    @feeds: `build`, dictionary, including meta info with the build of
            source image.
    @feeds: `build_type`, dict, with keys as build type names and values as
            type info corresponding to that build.
    """
    config = context.get('config')
    koji_build = KojiBuild(config)
    build = context.get('build')
    sc_build = None
    package_nvr = context.get('package_nvr')
    # Use the build directly if the build is for source container.
    if package_nvr and 'container-source' in package_nvr:
        if is_source_container_build(context, build):
            sc_build = build
    # Get the source container build if the input is a binary container.
    elif package_nvr and 'container' in package_nvr:
        sc_build = koji_build.get_latest_source_container_build(package_nvr)
    if sc_build:
        #  Add build id in the json.
        if "id" not in sc_build:
            sc_build["id"] = sc_build.get("build_id")
        # Get the binary build for the import source container nvr.
        koji_connector = KojiConnector(config)
        if package_nvr == sc_build.get('nvr'):
            msg = 'Found source container build %s for %s in Brew/Koji'
            engine.logger.info(msg % (sc_build.get('nvr'), package_nvr))
            binary_nvr = koji_connector.get_binary_nvr(package_nvr)
            binary_build = koji_connector.get_build(binary_nvr)
        else:
            binary_build = context.get('build')
        context['binary_build'] = binary_build
        context['build'] = sc_build
        context['build_type'] = koji_build.get_build_type(sc_build)

    else:
        err_msg = "This binary container has no mapping source container."
        engine.logger.error(err_msg)
        raise ValueError(err_msg) from None


def download_source_image(context, engine):
    """
    Download the container source image.
    With normalized parameters, returning an absolute path \
    to which the image is being downloaded.

    @requires: `config`, configuration from hub server. It's not always
                required.
    @requires: `client`, to communicate with hub server. It's not always
                required.
    @feeds: `tmp_src_filepath`, absolute path to the downloaded image.
    """
    tmp_dir = tempfile.mkdtemp(prefix='download_sc_',
                               dir=context.get('tmp_root_dir'))
    config = context.get('config')
    build = context.get('build')

    koji_connector = KojiConnector(config)
    arch = 'x86_64'
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
    tmp_dir = tempfile.mkdtemp(prefix='download_')
    config = context.get('config')
    build = context.get('build')
    koji_connector = KojiConnector(config)
    build_id = build.get('id')

    engine.logger.info('Start to download package source from Brew/Koji...')
    try:
        koji_connector.download_build_source(build_id, dest_dir=tmp_dir)
    except RuntimeError as err:
        nvr = build.get('nvr')
        err_msg = f'Failed to download source for {nvr} in Brew/Koji.' \
                  f' Reason: {err}'
        engine.logger.error(err_msg)
        raise RuntimeError(err_msg) from None

    tmp_src_filepath = os.path.join(tmp_dir, os.listdir(tmp_dir)[0])
    context['tmp_src_filepath'] = tmp_src_filepath

    build_type = context.get('build_type')
    if 'maven' in build_type:
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
        elif 'metadata' in src_dir:
            try:
                source_path = sc_handler.get_source_of_misc_component(
                    src_dir, nvr)
            except RuntimeError as err:
                err_msg = f"Failed to get source tarball for metadata: {err}"
                engine.logger.error(err_msg)
                raise RuntimeError(err_msg) from None
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
    @feeds: 'source_url' - string, package upstream source URL.
    @feeds: 'declared_license' - string, package declared license.
    """

    engine.logger.info("Start to get source package metadata...")
    src_filepath = context.get('tmp_src_filepath')
    pom_filepath = context.get('tmp_pom_filepath', None)
    build_type = context.get('build_type')
    build = context.get('build')

    package = None
    try:
        if 'rpm' in build_type:
            package = rpm_parse(src_filepath)
        elif pom_filepath is not None:
            package = maven_parse(pom_filepath)
        # TODO: Add support for other package types.
    except Exception as e:
        engine.logger.warning(str(e))

    if package is not None:
        # Package has below urls which could be referenced as source url:
        # homepage_url --> vcs_url --> code_view_url --> download_url
        # download_url is version related which is not preferred.
        # homepage_url: http://cxf.apache.org
        # vcs_url: git+http://gitbox.apache.org/repos/asf/cxf.git
        # code_view_url: https://gitbox.apache.org/repos/asf?p=cxf.git;a=summary    # noqa
        # download_url: https://pkg.freebsd.org/freebsd:10:x86:64/latest/All/dmidecode-2.12.txz    # noqa
        urls = ['homepage_url', 'vcs_url', 'code_view_url', 'download_url']
        for url in urls:
            if hasattr(package, url):
                context['source_url'] = getattr(package, url)
                break
        # Use declared_license from packagecode output which could support
        # more package types instead of rebuilding wheels.
        context['declared_license'] = package.declared_license

    # TODO: Update metadata for remote source.
    context['source_info'] = {
        "source": {
            "checksum": sha256sum(src_filepath),
            "name": os.path.basename(src_filepath),
            "url": context.get("source_url"),
            "archive_type": list(context['build_type'].keys())[0]
        },
        "component": {
            "name": build.get('name'),
            "version": build.get('version'),
            "release": build.get('release'),
            "arch": 'src',
            "type": context.get('comp_type'),
            "summary_license": context.get("declared_license", ""),
            "is_source": True
        }
    }
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
        config = context.get('config')
        license_flag = "license(" + config.get('LICENSE_SCANNER') + ")"
        copyright_flag = "copyright(" + config.get('COPYRIGHT_SCANNER') + ")"
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
    component_type = context.get('component_type')
    engine.logger.info('Start to prepare destination directory...')
    if component_type and component_type in ['SRPM', 'CONTAINER_IMAGE']:
        # TODO: Currently we don't store product and release data. so the
        #  import should not contain "product_release" or add it manually
        #  in database.
        if release:
            if isinstance(release, dict):
                short_name = release.get('short_name')
            else:
                short_name = release
        else:
            short_name = config.get('ORPHAN_CATEGORY')

        # Create source container metadata destination source directory.
        src_root = config.get('SRC_ROOT_DIR')
        if component_type == 'CONTAINER_IMAGE':
            metadata_dir = build.get('nvr') + '-metadata'
            src_dir = os.path.join(src_root, short_name, metadata_dir)
        else:
            src_dir = os.path.join(
                src_root, short_name, build.get('name'), build.get('nvr'))

        if os.path.exists(src_dir):
            shutil.rmtree(src_dir, ignore_errors=True)
        try:
            os.makedirs(src_dir)
        except OSError as err:
            msg = f"Failed to create directory {src_dir}: {err}"
            engine.logger.error(msg)
            raise RuntimeError(msg) from None
    # Remote source archives will be stored in a separate directory under
    # "SRC_ROOT_DIR".
    else:
        src_root = config.get('RS_SRC_ROOT_DIR')
        # `src_root` for remote source archives may not exist for the first
        # time unless explicitly created.
        if not os.path.exists(src_root):
            os.makedirs(src_root)
        src_dir = tempfile.mkdtemp(prefix='rs_', dir=src_root)
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
    @feeds: 'sc_lable', True or False, a flag for source container.
    """
    prepare_dest_dir(context, engine)
    config = context.get('config')
    tmp_src_filepath = context.get('tmp_src_filepath')
    src_dest_dir = context.get('src_dest_dir')

    # Unpack the source container image.
    sc_handler = SourceContainerHandler(config, tmp_src_filepath, src_dest_dir)
    engine.logger.info('Start to unpack source container image...')
    try:
        srpm_dir, rs_dir, misc_dir = sc_handler.unpack_source_container_image()
    except (ValueError, RuntimeError) as err:
        err_msg = "Failed to decompress file %s: %s" % (tmp_src_filepath, err)
        engine.logger.error(err_msg)
        raise RuntimeError(err_msg) from None
    engine.logger.info('Finished unpacking the source archives.')
    context['misc_dir'], context['srpm_dir'], context['rs_dir'] = \
        misc_dir, srpm_dir, rs_dir
    context['sc_lable'] = True


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

                if swhids:
                    context['source_info']['swhids'] = swhids

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


def send_package_data(context, engine):
    """
    Equivalent of the former "post"/"post_adhoc", which sends/posts
    results to hub. But exclude scan result, they posted in other step.
    """
    url = 'packageimporttransaction'
    cli = context.pop('client')
    package_nvr = context.get('package_nvr')
    component = package_nvr if package_nvr else context.get('rs_comp')
    engine.logger.info(f"Start to send {component} data to hub for further "
                       f"processing...")
    # Post data file name instead of post context data
    fd, tmp_file_path = tempfile.mkstemp(prefix='send_package_',
                                         dir=context.get('post_dir'))
    with os.fdopen(fd, 'w') as destination:
        json.dump(context.get("source_info"), destination, cls=DateEncoder)
    resp = cli.post(url, data={"file_path": tmp_file_path})
    context['client'] = cli
    try:
        # Raise it in case we made a bad request:
        # http://docs.python-requests.org/en/master/user/quickstart/#response-status-codes  # noqa
        resp.raise_for_status()
    except HTTPError:
        err_msg = f"Failed to save {package_nvr} data to db: {resp.text}"
        engine.logger.error(err_msg)
        raise RuntimeError(err_msg) from None
    finally:
        os.remove(tmp_file_path)
    engine.logger.info(f"Finished saving {component} data to database.")


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
            src_dir=src_dir, config=config, logger=engine.logger)
    (licenses, errors, has_exception) = scanner.scan()
    engine.logger.info("Done")
    scan_result = {
        "source_checksum": context.get("source_info").get("source").get(
            "checksum")}
    scan_result.update({
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
            src_dir=src_dir, config=config, logger=engine.logger)
    (copyrights, errors, has_exception) = scanner.scan()
    engine.logger.info("Done")
    scan_result = context.get('scan_result', {})
    if "source_checksum" not in scan_result:
        scan_result["source_checksum"] = context.get("source_info").get(
            "source").get("checksum")
    scan_result.update({
        "copyright_scan": context.get('copyright_scan'),
        "path_with_swhids": context.get('path_with_swhids'),
        "copyrights": {
            "data": copyrights,
            "errors": errors,
            "has_exception": has_exception
        }
    })
    context['scan_result'] = scan_result


def send_scan_result(context, engine):
    """
    Equivalent of the former "post"/"post_adhoc", which sends/posts
    scan results to hub.
    """
    if 'scan_result' not in context:
        return
    url = 'savescanresult'
    cli = context.pop('client')
    package_nvr = context.get('package_nvr')
    component = package_nvr if package_nvr else context.get('rs_comp')
    engine.logger.info(f"Start to send {component} scan result to hub for "
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
    @requires: `nvr`, string, the container nvr.
    @feeds: `components`, list of dictionary,
             components information of the container.
    """
    config = context.get('config')
    cc = ParentComponentsAsync(
        config.get('CORGI_API_PROD'), context.get('package_nvr'))
    return cc.get_components_data("CONTAINER_IMAGE")


def get_remote_source_components(context, engine):
    """
    Get remote source components in source container
    @requires: `config`, configurations from Hub.
    @requires: `package_nvr`, nvr of the container.
    @feeds: `rs_components`, remote source components in source container.
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
    @feeds: `components`, components found in the container.
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
    @requires: `rs_dir`, directory that store remote source after collate.
    """
    rs_types = ['GOLANG', 'YARN', 'PYPI', 'NPM']
    components = context.get('components')
    if any([True for rs_type in rs_types if rs_type in components.keys()]):
        engine.logger.info('Start to get remote source in source container...')
        config = context.get('config')
        src_dest_dir = context.get('src_dest_dir')
        sc_handler = SourceContainerHandler(config, dest_dir=src_dest_dir)
        rs_components = []
        for comp_type in rs_types:
            type_components = components.get(comp_type)
            if type_components:
                rs_components.extend(type_components)
        missing_components = sc_handler.get_container_remote_source(
            rs_components)
        if missing_components:
            engine.logger.error('Failed to get remote source for components:')
            for missing_component in missing_components:
                engine.logger.error(missing_component)
            context['missing_components'] = missing_components

        # Redefine the 'rs_dir' after collate remote source.
        context['rs_dir'] = os.path.join(context.get('src_dest_dir'), 'rs_dir')
        msg = "Finished getting remote source in source container."
        engine.logger.info(msg)


def save_group_components(context, engine):
    """
    Send container/module components to hub, then store the components.
    """
    url = 'savegroupcomponents'
    cli = context.pop('client')
    package_nvr = context.get('package_nvr')
    if 'image' in context.get('build_type'):
        component_type = 'CONTAINER_IMAGE'
    else:
        component_type = 'RHEL_MODULE'
    data = {
        'components': context.get('components'),
        'product_release': context.get('product_release'),
        'component_type': component_type
    }
    msg = f'Start to save components in {component_type} {package_nvr}...'
    engine.logger.info(msg)
    fd, tmp_file_path = tempfile.mkstemp(
        prefix='scan_group_components_', dir=context.get('post_dir'))
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
    config = context.get('config')
    engine.logger.info("Start to get module components data...")
    mc = ParentComponentsAsync(
        config.get('CORGI_API_PROD'), context.get('package_nvr'))
    context['components'] = mc.get_components_data('RHEL_MODULE')
    engine.logger.info("Finished getting module components data.")


def fork_detail_type_components_imports(
        context, engine, nvr_list, src_dir, comp_type):
    """
    In a source container, it has different type of component. The different
    components have different src_dir. This function will be defined the post
    data for the different type component.
    """
    cli = context.get('client')
    url = '/sources/import/'
    msg = 'Start to fork imports for {} components...'.format(len(nvr_list))
    data = {
        'component_type': comp_type,
        'src_dir': src_dir,
        'package_nvrs': nvr_list,
        'license_scan': context.get('license_scan'),
        'copyright_scan': context.get('copyright_scan')
    }
    engine.logger.info(msg)
    cli.post(url, data=data)
    msg = '-- Forked import tasks for below source components:{}'.format(
            "\n\t" + "\n\t".join(nvr_list))
    engine.logger.info(msg)
    engine.logger.info('Done')


def fork_remote_source_components_imports(context, engine, rs_comps, src_dir):
    """
    In a source container, it has different type of component. The different
    components have different src_dir. This function will be defined the post
    data for the different remote source component.
    """
    cli = context.get('client')
    url = '/sources/import/'
    msg = 'Start to fork imports for {} remote source components...'.format(
        len(rs_comps))
    data = {
        'src_dir': src_dir,
        'rs_comps': rs_comps,
        'license_scan': context.get('license_scan'),
        'copyright_scan': context.get('copyright_scan')
    }
    engine.logger.info(msg)
    cli.post(url, data=data)
    components = ""
    for rs_comp in rs_comps:
        components += "\n\t" + 'name(%s) version(%s) type(%s)' % (
            rs_comp.get('name'), rs_comp.get('version'), rs_comp.get('type'))
    msg = f'-- Forked import tasks for below source components:{components}'
    engine.logger.info(msg)
    engine.logger.info('Done')


def fork_components_imports(context, engine):
    """
    Fork components tasks
    """
    components = context.get('components')
    srpm_nvr_list = get_nvr_list_from_components(components, 'SRPM')

    # Fork source RPM component tasks.
    if srpm_nvr_list:
        fork_detail_type_components_imports(
            context, engine, srpm_nvr_list, context.get('srpm_dir'), 'SRPM')

    # Fork container-component tasks with the misc metadata files.
    if components.get('CONTAINER_IMAGE'):
        fork_detail_type_components_imports(
            context, engine, [context.get('package_nvr')],
            context.get('misc_dir'), 'CONTAINER_IMAGE')

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
    # Different workflows could be used for different build types
    IF_ELSE(
        lambda o, e: 'image' in o.get('build_type') and not o.get('component_type'), # noqa
        # Task flow for image build
        [
            get_source_container_build,
            download_source_image,
            unpack_container_source_archive,
            get_container_components,
            save_group_components,
            get_container_remote_source,
            fork_components_imports,
        ],
        [
            IF_ELSE(
                lambda o, e: 'module' in o.get('build_type'),
                # Task flow for module
                [
                    get_module_components_from_corgi,
                    save_group_components,
                ],
                # Task flow for source scan
                [
                    download_component_source,
                    get_source_metadata,
                    check_source_scan_status,
                    IF(
                        lambda o, e: not o.get("source_scanned"),
                        [
                            unpack_source,
                            deduplicate_source,
                            send_package_data,
                            IF(
                                lambda o, e: o.get('license_scan_req'),
                                license_scan,
                             ),
                            IF(
                                lambda o, e: o.get('copyright_scan_req'),
                                copyright_scan,
                            ),
                            send_scan_result,
                        ],
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
    send_scan_result,
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
