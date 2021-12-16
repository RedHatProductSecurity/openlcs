from workflow.patterns.controlflow import IF

from pelcd2.pelcflow.task_wrapper import WorkflowWrapperTask
from pelcd2.celery import app


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
    Exclude files that were already in db, and returns a subset of source
    directory with only files unseen before.

    Note: this requires to traverse the whole source directory, get
    each file hash and check file existence in db, thus could be
    resource intensive.
    """
    raise NotImplementedError


def split_and_repack_source(context, engine):
    """
    Accept a source directory, split it into smaller directories(if
    necessary), and repack the directories into archives such that each
    archive could be deposited successfuly into swh.

    Note that original directory hierarchy should be preserved,
    see also `retrieve_source_from_swh` below.
    """
    raise NotImplementedError


def upload_to_deposit(context, engine):
    """
    Accept a list of archives, upload the archives into swh using
    the deposit api.
    """
    raise NotImplementedError


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
    split_and_repack_source,
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
        from pelcd2.pelcflow.core import PelcWorkflowEngine

        wfe = PelcWorkflowEngine()
        wfe.setWorkflow(flow)
        for arg in args:
            arg.setdefault('task_id', self.request.id)
        wfe.process(list(args))

    return task


register_task_flow('pelcflow.tasks.flow_default', flow_default)
register_task_flow('pelcflow.tasks.flow_retry', flow_retry)
