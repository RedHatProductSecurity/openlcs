import datetime
import glob
import json
import os
import shutil
import socket
import tarfile
import tempfile
from requests.exceptions import HTTPError
from workflow.patterns.controlflow import IF

from pelcd.pelcflow.task_wrapper import WorkflowWrapperTask
from pelcd.celery import app
from pelc.libs.brewconn import BrewConnector
from pelc.libs.deposit import UploadToDeposit
from pelc.libs.scanner import LicenseScanner
from pelc.libs.scanner import CopyrightScanner
from pelc.libs.driver import PelcClient
from pelc.libs.logging import get_task_logger
from pelc.libs.parsers import sha256sum
from pelc.libs.swh_tools import get_swhids_with_paths
from pelc.libs.unpack import UnpackArchive


def get_config(context, engine):
    """
    Get the hub configure information.

    @requires: 'task_id', id of the task. needed while initializing logger

    @feeds: `config`, dict, configurations obtained from Hub.
    @feeds: `client`, a PelcClient instance, to communicate with Hub.
    @feeds: `tmp_root_dir`, destination dir where temporary source
                            will be placed.
    @feeds: `post_dir`, destination dir where temporary post/adhoc_post data
                        file will be placed.
    """
    config = {}

    # Get config data
    try:
        task_id = context.get('task_id')
        client = PelcClient(task_id=task_id)
        resp = client.get('obtain_config')
        if resp.status_code == 200:
            config = resp.json()
    except RuntimeError as err:
        err_msg = f'Failed to get config data. Reason: {err}'
        raise RuntimeError(err_msg) from None
    # One-time file based logger configuration for each task.
    logger_dir = config.get("LOGGER_DIR")
    engine.logger = engine.log = get_task_logger(logger_dir, task_id)

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
    from pelc.libs.download import BrewBuild
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


def download_source(context, engine):
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

    # FIXME: this is migrated from existing code, but UGLY.
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

    context['source_info'] = {
        "source": {
            "checksum": sha256sum(tmp_src_filepath),
            "name": os.path.basename(tmp_src_filepath),
            "archive_type": list(context['build_type'].keys())[0]
        },
        "package": {
            "nvr": context.get("package_nvr")
        }
    }
    engine.logger.info('Finished downloading source.')


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
            context['path_with_swhids'] = list(zip(paths, path_swhids))
            swhids = [path_swhid[1] for path_swhid in path_swhid_list]

            try:
                # Deduplicate files.
                response = get_data_using_post(context.get('client'),
                                               '/check_duplicate_files/',
                                               {'swhids': swhids})
                existing_swhids = response.get('existing_swhids')
                if existing_swhids:
                    swhids = list(set(swhids).difference(set(existing_swhids)))
                    for path, swhid in path_swhid_list:
                        if swhid in existing_swhids:
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
                } for (path, swhid) in path_swhid_list]
            except RuntimeError as err:
                err_msg = f"Failed to check duplicate files. Reason: {err}"
                engine.logger.error(err_msg)
                raise RuntimeError(err_msg) from None
    else:
        err_msg = "Failed to find unpack source directory path."
        engine.logger.error(err_msg)
        raise RuntimeError(err_msg)
    engine.logger.info("Finished deduplicating source.")


def check_duplicate_source(context, engine):
    """
    Check if the source exist in database.
    """
    checksum = context['source_info']['source']['checksum']
    try:
        response = get_data_using_post(context.get('client'),
                                       '/check_duplicate_source/',
                                       {"checksum": checksum})
    except RuntimeError as err:
        engine.logger.error(err)
        raise RuntimeError(err) from None
    context['source_exist'] = response.get('source_exist')


def repack_source(context, engine):
    """
    Repack the unpacked source into archives so that each archive could be
    deposited successfully into swh.

    @requires: `src_dest_dir`,the archive unpack directory
    @requires: `archive_name`, archive original name which will be saved in swh
    @feeds: `tmp_repack_archive_path`, temporary repack directory
    """
    # Skip repack source if source exist.
    check_duplicate_source(context, engine)
    if context.get('source_exist'):
        return

    engine.logger.info('Start to repack source...')
    src_dest_dir = context.get("src_dest_dir")
    archive_name = context.get('package_nvr') + ".tar.gz"
    context['archive_name'] = archive_name
    tmp_repack_archive_path = os.path.join(tempfile.mkdtemp(prefix='repack_'),
                                           archive_name)
    # https://docs.python.org/3/library/tarfile.html
    with tarfile.open(tmp_repack_archive_path, mode='w:gz') as tar:
        tar.add(src_dest_dir, arcname=os.path.basename(src_dest_dir))
    context['tmp_repack_archive_path'] = tmp_repack_archive_path
    engine.logger.info("Finished repacking source.")


def upload_archive_to_deposit(context, engine):
    """
    Accept a directory path of unpack archives, upload the archives into swh
    using the deposit api.

    @requires: `config`, configuration from hub server
    @requires: `archive_name`, original archive name which will be saved in swh
    @requires: `tmp_repack_archive_path`, temporary repacked archive path
    @feeds: Upload archive to deposit, and save archive metadata in pelc and
            delete temporary archive
    """
    # Skip update archive to deposit if source exist.
    if context.get('source_exist'):
        return

    tmp_repack_archive_path = context.get('tmp_repack_archive_path')
    archive_name = context.get('archive_name')
    logger = engine.logger
    _settings = context.get('config')
    _deposit = UploadToDeposit(_settings)

    engine.logger.info(f"Start to upload archive {archive_name} to deposit...")
    try:
        ret_output = _deposit.deposit_archive(tmp_repack_archive_path,
                                              archive_name)
        if not ret_output:
            err_msg = "Failed to upload archive to deposit. " \
                      "Cannot find the deposit result."
            raise RuntimeError(err_msg)
    except RuntimeError as err:
        err_msg = f"Failed to upload archive to deposit, Reason: {err}"
        logger.error(err_msg)
        raise RuntimeError(err_msg) from None

    # Check deposit status
    deposit_id = _deposit.get_deposit_id(ret_output)
    try:
        upload_status = _deposit.check_deposit_archive_status(deposit_id)
    except TimeoutError as err:
        err_msg = f"Check deposit archive timeout, Reason: {err}"
        logger.error(err_msg)
        raise TimeoutError(err_msg) from None

    if upload_status == "done":
        logger.info(
            f"Successfully uploaded archive {archive_name} to deposit.")
    else:
        logger.error(f"Failed to upload archive {archive_name} to deposit.")

    # After upload to deposit success , delete repack archive
    shutil.rmtree(tmp_repack_archive_path, ignore_errors=True)
    logger.info(f"Finished uploading archive {archive_name} to deposit.")


def retrieve_source_from_swh(context, engine):
    """
    Accept a build or package nvr, retrieve the source directory tree
    from swh. The source may correspond to various archives(splitted)
    in swh, we need to make sure the source directory retrieved(from
    multiple archives) is consistent with the original source tree(the
    directory we get after `unpack_source`).
    """
    raise NotImplementedError


class DateEncoder(json.JSONEncoder):
    def default(self, o):    # pylint: disable=E0202
        if isinstance(o, datetime.datetime):
            return o.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(o, datetime.date):
            return o.strftime("%Y-%m-%d")
        else:
            return json.JSONEncoder.default(self, o)


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
    failure = False
    try:
        # Raise it in case we made a bad request:
        # http://docs.python-requests.org/en/master/user/quickstart/#response-status-codes  # noqa
        resp.raise_for_status()
    except HTTPError:
        err_msg = f"Failed to save {package_nvr} data to db: {resp.text}"
        engine.logger.error(err_msg)
        failure = True
        raise RuntimeError(err_msg) from None
    finally:
        # Remove temporarily created files/directories under /tmp.
        tmp_src_filepath = context.get('tmp_src_filepath')
        if tmp_src_filepath:
            tmp_dir = os.path.dirname(tmp_src_filepath)
            if os.path.exists(tmp_dir) and not failure:
                shutil.rmtree(tmp_dir, ignore_errors=True)
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
    # Scanner could be provided when multiple scanners supported in future.
    engine.logger.info("Start to scan source licenses with Scancode...")
    scanner = LicenseScanner(
            src_dir=src_dir, config=config, logger=engine.logger)
    (licenses, errors, has_exception) = scanner.scan()
    engine.logger.info("Done")
    scan_result = context.get('scan_result', {})
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
    failure = False
    try:
        resp.raise_for_status()
    except HTTPError:
        err_msg = f"Failed to save scan result to database: {resp.text}"
        engine.logger.error(err_msg)
        failure = True
        raise RuntimeError(err_msg) from None
    finally:
        # Remove temporarily created files/directories under /tmp.
        tmp_src_filepath = context.get('tmp_src_filepath')
        if tmp_src_filepath:
            tmp_dir = os.path.dirname(tmp_src_filepath)
            if os.path.exists(tmp_dir) and not failure:
                shutil.rmtree(tmp_dir, ignore_errors=True)
    engine.logger.info("Finished saving scan result to database.")


def clean_up(context, engine):
    """
    Remove obsolete directories, garbages generated during the flow.

    This could also be done in the task success/failure callback,
    once we implement it there, we should remove this function.
    """


flow_default = [
    get_config,
    get_build,
    download_source,
    unpack_source,
    # PVLEGAL-1840 is to support splitting a large archive
    # split_source,
    repack_source,
    # FIXME: upload_to_deposit/license_scan/copyright_scan are time
    # consuming, we don't have an agreement yet whether they should
    # be run one after another or in parallel.
    upload_archive_to_deposit,
    deduplicate_source,
    send_package_data,
    IF(
        lambda o, e: o.get('license_scan'),
        license_scan,
    ),
    IF(
        lambda o, e: o.get('copyright_scan'),
        copyright_scan,
    ),
    send_scan_result,
    clean_up,
]

flow_retry = [
    get_config,
    retrieve_source_from_swh,
    IF(
        lambda o, e: o.get('license_scan'),
        license_scan,
    ),
    IF(
        lambda o, e: o.get('copyright_scan'),
        copyright_scan,
    ),
    send_scan_result,
    clean_up,
]


def register_task_flow(name, flow, **kwargs):
    @app.task(name=name, bind=True, base=WorkflowWrapperTask, **kwargs)
    def task(self, *args):
        # Note that the imports that this function requires must be done
        # inside since our code will not be running in the global context.
        from pelcd.pelcflow.core import PelcWorkflowEngine

        wfe = PelcWorkflowEngine()
        wfe.setWorkflow(flow)
        for arg in args:
            arg.setdefault('task_id', self.request.id)
        wfe.process(list(args))

    return task


register_task_flow('pelcflow.tasks.flow_default', flow_default)
register_task_flow('pelcflow.tasks.flow_retry', flow_retry)
