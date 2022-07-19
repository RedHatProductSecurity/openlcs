import glob
import json
import os
import shutil
import socket
# import tarfile
import tempfile
from requests.exceptions import HTTPError

from workflow.patterns.controlflow import IF
from workflow.patterns.controlflow import IF_ELSE
from packagedcode.rpm import parse as rpm_parse
from packagedcode.maven import parse as maven_parse

from openlcsd.flow.task_wrapper import WorkflowWrapperTask
from openlcsd.celery import app
from openlcs.libs.brewconn import BrewConnector
from openlcs.libs.components import ContainerComponentsAsync
# from openlcs.libs.deposit import UploadToDeposit
from openlcs.libs.scanner import LicenseScanner
from openlcs.libs.scanner import CopyrightScanner
from openlcs.libs.driver import OpenlcsClient
from openlcs.libs.logger import get_task_logger
from openlcs.libs.parsers import sha256sum
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
    # directory under "SRC_ROOT_DIR", see also PVLEGAL-1044
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
    Get build from brew.

    @requires: `config`, configuration from hub server.
    @requires: `package_nvr`, `brew_tag`, `package_name`.
    @feeds: `build`, dictionary, including meta info with the brew build.
    @feeds: `build_type`, dict, with keys as build type names and values as
                type info corresponding to that type.
    """
    from openlcs.libs.download import BrewBuild
    config = context.get('config')
    brew_build = BrewBuild(config)
    build = brew_build.get_build(
        context.get('package_nvr'),
        context.get('brew_tag'),
        context.get('package_name'),
        context.get('rpm_nvra'),
    )
    build_type = brew_build.get_build_type(build)
    context['build_type'] = build_type
    context['build'] = build


def get_osbs_build_kind(build):
    """
    Get the osbs build type from build extra.
    """
    extra = build.get('extra', None)
    osbs_build = extra.get('osbs_build') if extra else None
    return osbs_build.get('kind') if osbs_build else None


def is_source_container_build(build):
    """
    Check whether the build is a source container build.
    @requires: `build`, dictionary, the build got via brew API.
    @feeds: True, False
    """
    container_type = get_osbs_build_kind(build)
    return container_type == 'source_container_build'


def get_source_container_build(context, engine):
    """
    Get Source container build with brew API.
    @requires: `config`, configuration from hub server.
    @requires: `build`, dictionary, including meta info with the brew build.
    @feeds: `build`, dictionary, including meta info with the brew build of
            source image.
    @feeds: `build_type`, dict, with keys as build type names and values as
            type info corresponding to that build.
    """
    from libs.download import BrewBuild
    config = context.get('config')
    brew_build = BrewBuild(config)
    build = context.get('build')
    sc_build = None
    package_nvr = context.get('package_nvr')
    # Use the build directly if the build is for source container.
    if package_nvr and 'container-source' in package_nvr:
        if is_source_container_build(build):
            sc_build = build
    # Get the source container build if the input is a binary container.
    elif package_nvr and 'container' in package_nvr:
        # TODO: try to find the source container for binary container
        pass

    if sc_build:
        if package_nvr != sc_build.get('nvr'):
            msg = 'Found source container build %s for %s in Brew'
            engine.logger.info(msg % (sc_build.get('nvr'), package_nvr))
        if "id" not in sc_build:
            sc_build["id"] = sc_build.get("build_id")
        build_type = brew_build.get_build_type(sc_build)
        context['build'] = sc_build
        context['build_type'] = build_type


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

    brew_conn = BrewConnector(config)
    arch = 'x86_64'
    msg = "Start to download container source image build from Brew, "
    msg += "please wait for the task log update..."
    engine.logger.info(msg)
    brew_conn.download_container_image_archives(build, tmp_dir, arch)
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
    brew_conn = BrewConnector(config)
    build_id = build.get('id')

    engine.logger.info('Start to download package source from Brew...')
    try:
        brew_conn.download_build_source(build_id, dest_dir=tmp_dir)
    except RuntimeError as err:
        nvr = build.get('nvr')
        err_msg = f'Failed to download source for {nvr} in Brew. Reason: {err}'
        engine.logger.error(err_msg)
        raise RuntimeError(err_msg) from None

    tmp_src_filepath = os.path.join(tmp_dir, os.listdir(tmp_dir)[0])
    context['tmp_src_filepath'] = tmp_src_filepath

    build_type = context.get('build_type')
    if 'maven' in build_type:
        try:
            pom_path = brew_conn.get_pom_pathinfo(build_id=build.get('id'))
        except ValueError as e:
            context['tmp_pom_filepath'] = None
            engine.logger.warning("%s" % e)
        else:
            brew_conn.download_pom(pom_path, tmp_dir)
            pom_files = glob.glob("%s/*.pom" % tmp_dir)
            if pom_files:
                context['tmp_pom_filepath'] = pom_files[0]

    engine.logger.info('Finished downloading source.')


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
        # download_url is version related which is not prefered.
        # homepage_url: http://cxf.apache.org
        # vcs_url: git+http://gitbox.apache.org/repos/asf/cxf.git
        # code_view_url: https://gitbox.apache.org/repos/asf?p=cxf.git;a=summary    # noqa
        # download_url: https://pkg.freebsd.org/freebsd:10:x86:64/latest/All/dmidecode-2.12.txz    # noqa
        urls = ['homepage_url', 'vcs_url', 'code_view_url', 'download_url']
        for url in urls:
            if getattr(package, url):
                context['source_url'] = getattr(package, url)
                break
        # Use declared_license from packagecode output which could support
        # more package types instead of rebuilding wheels.
        context['declared_license'] = package.declared_license

    context['source_info'] = {
        "source": {
            "checksum": sha256sum(src_filepath),
            "name": os.path.basename(src_filepath),
            "url": context.get("source_url"),
            "archive_type": list(context['build_type'].keys())[0]
        },
        "package": {
            "nvr": context.get("package_nvr"),
            "sum_license": context.get("declared_license"),
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
    For builds from brew, if destination dir already exists, remove it
    recursively and create new one.

    @requires: `config`, configuration from hub server.
    @requires: `build`, meta info with the brew build.
    @feeds: `src_dest_dir`, destination dir where source will be placed.
    """
    config = context.get('config')
    build = context.get('build')
    release = context.get('product_release')
    engine.logger.info('Start to prepare destination directory...')
    if build:
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

        src_dir = os.path.join(config.get('SRC_ROOT_DIR'), short_name,
                               build.get('name'), build.get('nvr'))

        if os.path.exists(src_dir):
            shutil.rmtree(src_dir, ignore_errors=True)
        try:
            os.makedirs(src_dir)
        except OSError as e:
            msg = "Failed to create directory {0}: {1}".format(
                src_dir, e)
            engine.logger.error(msg)
            raise RuntimeError(msg) from None
    else:
        msg = "Failed to get build and release information."
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


# def repack_source(context, engine):
#     """
#     Repack the unpacked source into archives so that each archive could be
#     deposited successfully into swh.
#
#     @requires: `source_api_url`, string, the restful API url of the source.
#     @requires: `src_dest_dir`,the archive unpack directory.
#     @requires: `archive_name`, archive original name which will be saved in
#                SWH.
#     @feeds: `tmp_repack_archive_path`, temporary repack directory.
#     """
#     # Skip repack source if source exist.
#     if context.get('source_api_url'):
#         return
#
#     engine.logger.info('Start to repack source...')
#     src_dest_dir = context.get("src_dest_dir")
#     archive_name = context.get('package_nvr') + ".tar.gz"
#     context['archive_name'] = archive_name
#     tmp_repack_archive_path = os.path.join(
#             tempfile.mkdtemp(prefix='repack_'), archive_name)
#     # https://docs.python.org/3/library/tarfile.html
#     with tarfile.open(tmp_repack_archive_path, mode='w:gz') as tar:
#         tar.add(src_dest_dir, arcname=os.path.basename(src_dest_dir))
#     context['tmp_repack_archive_path'] = tmp_repack_archive_path
#     engine.logger.info("Finished repacking source.")
#
#
# def upload_archive_to_deposit(context, engine):
#     """
#     Accept a directory path of unpack archives, upload the archives into swh
#     using the deposit api.
#
#     @requires: `source_api_url`, string, the restful API url of the source.
#     @requires: `config`, configuration from hub server.
#     @requires: `archive_name`, original archive name which will be saved in
#                SWH.
#     @requires: `tmp_repack_archive_path`, temporary repacked archive path.
#     @feeds: Upload archive to deposit, and save archive metadata in openlcs
#             and delete temporary archive.
#     """
#     # Skip update archive to deposit if source exist.
#     if context.get('source_api_url'):
#         return
#
#     tmp_repack_archive_path = context.get('tmp_repack_archive_path')
#     archive_name = context.get('archive_name')
#     logger = engine.logger
#     _settings = context.get('config')
#     _deposit = UploadToDeposit(_settings)
#
#     engine.logger.info(f"Start to upload {archive_name} to deposit...")
#     try:
#         ret_output = _deposit.deposit_archive(tmp_repack_archive_path,
#                                               archive_name)
#         if not ret_output:
#             err_msg = "Failed to upload archive to deposit. " \
#                       "Cannot find the deposit result."
#             raise RuntimeError(err_msg)
#     except RuntimeError as err:
#         err_msg = f"Failed to upload archive to deposit, Reason: {err}"
#         logger.error(err_msg)
#         raise RuntimeError(err_msg) from None
#
#     # Parse deposit result to get deposit id.
#     try:
#         deposit_id = _deposit.get_deposit_id(ret_output)
#         if deposit_id:
#             info_msg = f'Successfully parsed deposit result to get ' \
#                        f'deposit id: {deposit_id}'
#             logger.info(info_msg)
#         else:
#             err_msg = f'Failed to get deposit id from the deposit result: ' \
#                       f'{ret_output}'
#             logger.error(err_msg)
#             raise RuntimeError(err_msg)
#     except RuntimeError as err:
#         err_msg = f"Failed to get deposit id, Reason: {err}"
#         logger.error(err_msg)
#         raise RuntimeError(err_msg) from None
#
#     # Check deposit status.
#     try:
#         upload_status = _deposit.check_deposit_archive_status(deposit_id)
#         if upload_status == "done":
#             logger.info(
#                 f"Successfully uploaded archive {archive_name} to deposit.")
#         else:
#             logger.error(
#                 f"Failed to upload archive {archive_name} to deposit.")
#     except TimeoutError as err:
#         err_msg = f"Check deposit archive timeout, Reason: {err}"
#         logger.error(err_msg)
#         raise TimeoutError(err_msg) from None
#     except RuntimeError as err:
#         err_msg = f"Check deposit archive failed, Reason: {err}"
#         logger.error(err_msg)
#         raise RuntimeError(err_msg) from None
#
#     # After upload to deposit success , delete repack archive
#     shutil.rmtree(tmp_repack_archive_path, ignore_errors=True)
#     logger.info(f"Finished uploading archive {archive_name} to deposit.")
#
#
# def retrieve_source_from_swh(context, engine):
#     """
#     Accept a build or package nvr, retrieve the source directory tree
#     from swh. The source may correspond to various archives(splitted)
#     in swh, we need to make sure the source directory retrieved(from
#     multiple archives) is consistent with the original source tree(the
#     directory we get after `unpack_source`).
#     """
#     raise NotImplementedError


def send_package_data(context, engine):
    """
    Equivalent of the former "post"/"post_adhoc", which sends/posts
    results to hub. But exclude scan result, they posted in other step.
    """
    url = 'packageimporttransaction'
    cli = context.pop('client')
    package_nvr = context.get('package_nvr')
    engine.logger.info(f"Start to send {package_nvr} data to hub for further "
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
    engine.logger.info(f"Finished saving {package_nvr} data to database.")


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
    engine.logger.info(f"Start to send {package_nvr} scan result to hub for "
                       f"further processing...")

    fd, tmp_file_path = tempfile.mkstemp(prefix='scan_result_',
                                         dir=context.get('post_dir'))
    with os.fdopen(fd, 'w') as destination:
        json.dump(context.get("scan_result"), destination, cls=DateEncoder)
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


def get_components_from_corgi(context, engine):
    """
    Get components information from Corgi.
    @requires: `nvr`, string, the container nvr.
    @requires: `components`, list of dictionary,
                components information of the container.
    """
    engine.logger.info('Start to get components data from Corgi...')
    config = context.get('config')
    base_url = os.path.join(config.get('CORGI_API_ROOT'), "components")
    cc = ContainerComponentsAsync(base_url, context.get('package_nvr'))
    context['components'] = cc.get_components_data()
    engine.logger.info('Finished getting components data from Corgi.')


def unpack_container_source_archive(context, engine):
    raise NotImplementedError


def get_component_source_path(context, engine):
    raise NotImplementedError


def fork_component_imports(context, engine):
    raise NotImplementedError


flow_default = [
    get_config,
    get_build,
    # Different workflows could be used for different build types
    IF_ELSE(
        lambda o, e: 'image' in o.get('build_type'),
        # Task flow for image build
        [
            # Collect container components from Corgi
            get_components_from_corgi,
            # Get the container source build
            get_source_container_build,
            # Download the source image from Brew
            download_source_image,
            # Unpack the source image
            unpack_container_source_archive,
            # Get the source path for each component from contaner source
            # For components failed to get a source path, exception warning
            # should be logged.
            get_component_source_path,
            # Fork the import task for each component
            fork_component_imports
        ],

        # Task flow for other build types
        [
            download_package_archive,
            get_source_metadata,
            check_source_scan_status,
            IF(
                lambda o, e: not o.get("source_scanned"),
                [
                    unpack_source,
                    # SWH is suspended, comment related codes out.
                    # TODO: OLCS-75 is for splitting a large archive
                    # split_source,
                    # repack_source,
                    # upload_archive_to_deposit,
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
                ]
            )
        ]
    )
]

flow_retry = [
    get_config,
    # TODO: need a source policy for retry scanning
    # retrieve_source_from_swh,
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
