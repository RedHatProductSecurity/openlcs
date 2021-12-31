import os.path
import shutil
import tarfile

from workflow.patterns.controlflow import IF
from pelcd.pelcflow.task_wrapper import WorkflowWrapperTask
from pelcd.celery import app
from pelc.libs.deposit import UploadToDeposit


def get_config(context, engine):
    raise NotImplementedError


def get_build(context, engine):
    """
    Get build from brew.
    """
    raise NotImplementedError


def download_source(context, engine):
    """
    Download source of given build/archive.
    """
    raise NotImplementedError


def unpack_source(context, engine):
    """
    Recursively unpack sources of given build/archive.
    """
    raise NotImplementedError


def get_unprocessed_files(context, engine):
    """
    Exclude files that were already in db,
    and returns a subset of source
    directory with only files unseen before.

    Note: this requires to traverse the whole source directory, get
    each file hash and check file existence in db, thus could be
    resource intensive.
    """
    raise NotImplementedError


def repack_source(context, engine):
    """
    Repack the directories into archives so that each
    archive could be deposited successfully into swh.

    @requires: `unpack_source_dir_path`,the archive unpack directory
    @requires: `archive_name`, archive original name
                which will be saved in swh
    @requires: `tmp_filepath`, temporary repacked archived path
    @feeds: `tmp_repack_archive_path`,temporary repack directory
    """
    # unpack_source_dir_path is unpacked path of archive file
    unpack_source_dir_path = context.get("unpack_source_dir_path")
    archive_name = context.get('archive_name')
    tmp_repack_dir_filepath = context.get('tmp_filepath')
    tmp_repack_archive_path = f'{tmp_repack_dir_filepath}/{archive_name}'
    # https://docs.python.org/3/library/tarfile.html
    with tarfile.open(tmp_repack_archive_path, mode='w:gz') as tar:
        tar.add(unpack_source_dir_path,
                arcname=os.path.basename(unpack_source_dir_path))
    context.update({'tmp_repack_archive_path': tmp_repack_archive_path})


def upload_to_deposit(context, engine):
    """
    Accept a directory path of unpack archives,
    upload the archives into swh using
    the deposit api.

    @requires: `config`, configuration from hub server
    @requires: `archive_name`, archive original name which will saved in swh
    @requires: `tmp_repack_archive_path`, temporary repacked archived path
    @feeds: Upload archive to deposit, and save archive metadata in pelc and
            delete temporary archive
    """
    tmp_repack_archive_path = context.get('tmp_repack_archive_path')
    archive_name = context.get('archive_name')
    logger = engine.logger
    _settings = context.get('config')
    _deposit = UploadToDeposit(_settings)
    ret_output = None
    upload_status = None

    # Start to upload to deposit
    try:
        ret_output = _deposit.deposit_archive(
                tmp_repack_archive_path,
                archive_name,
        )
    except RuntimeError as err:
        err_msg = "Upload to deposit timeout,Reason: {}".format(err)
        logger.error(err_msg)
        raise RuntimeError(err_msg) from None

    if not ret_output:
        raise RuntimeError("Upload deposit failed, please check log")
    deposit_id = _deposit.get_deposit_id(ret_output)

    # Check deposit status
    try:
        upload_status = _deposit.check_deposit_archive_status(
                            deposit_id
                        )
    except TimeoutError as err:
        err_msg = "Check deposit archive timeout, Reason: {}".format(err)
        logger.error(err_msg)
        raise TimeoutError(err_msg) from None

    if upload_status == "done":
        logger.info("Upload to deposit success")
    else:
        logger.error("Upload to deposit failed")
    logger.info(f"Start to save {archive_name} metadata to database")

    # TODO update status for archive in database
    _deposit.save_data_to_pelc()

    # After upload to deposit success , delete repack archive
    tmp_repack_archive_path = context.get('tmp_repack_archive_path')
    logger.info(f"Remove {archive_name} in disk")
    shutil.rmtree(tmp_repack_archive_path)
    logger.info(f"Upload archive {archive_name} finished")


def retrieve_source_from_swh(context, engine):
    """
    Accept a build or package nvr, retrieve the source directory tree
    from swh. The source may correponds to various archives(splitted)
    in swh, we need to make sure the source directory retrieved(from
    multiple archives) is consistent with the original source tree(the
    directory we get after `unpack_source`).
    """
    raise NotImplementedError


def license_scan(context, engine):
    raise NotImplementedError


def copyright_scan(context, engine):
    raise NotImplementedError


def send_result(context, engine):
    """
    Equalvalent of the former "post"/"post_adhoc", which sends/posts
    results to hub.
    """
    raise NotImplementedError


def clean_up(context, engine):
    """
    Remove obsolete directories, garbages generated during the flow.

    This could also be done in the task success/failure callback,
    once we implement it there, we should remove this function.
    """
    raise NotImplementedError


flow_default = [
    get_config,
    get_build,
    download_source,
    unpack_source,
    get_unprocessed_files,
    # If add the split large archive function
    # please check task PVLEGAL-1840
    # split_source,
    repack_source,
    # FIXME: upload_to_deposit/license_scan/copyright_scan are time
    # consuming, we don't have an agreement yet whether they should
    # be run one after another or in parallel.
    upload_to_deposit,
    IF(
        lambda o, e: o.get('license_scan'),
        license_scan,
    ),
    IF(
        lambda o, e: o.get('copyright_scan'),
        copyright_scan,
    ),
    send_result,
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
    send_result,
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
