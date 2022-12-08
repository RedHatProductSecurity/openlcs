import celery
import os
from commoncode.fileutils import delete


class WorkflowWrapperTask(celery.Task):

    abstract = True

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        """Handler called after the task returns."""
        comp_type = args[0].get('component_type')
        # Only keep uncompressed sources for container
        if comp_type != 'OCI' or args[0].get('parent'):
            src_dest_dir = args[0].get('src_dest_dir')
            if src_dest_dir and os.path.exists(src_dest_dir):
                delete(src_dest_dir)
        # Only keep the source tarball for failed container components
        if status == 'FAILURE' and 'src_dir' in args[0]:
            pass
        else:
            tmp_src_filepath = args[0].get('tmp_src_filepath')
            if tmp_src_filepath and os.path.exists(tmp_src_filepath):
                delete(tmp_src_filepath)
        super().after_return(
            status, retval, task_id, args, kwargs, einfo)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """This is run by the worker when the task fails."""
        super().on_failure(exc, task_id, args, kwargs, einfo)

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """This is run by the worker when the task is to be retried."""
        super().on_retry(exc, task_id, args, kwargs, einfo)

    def on_success(self, retval, task_id, args, kwargs):
        """Run by the worker if the task executes successfully."""
        super().on_success(retval, task_id, args, kwargs)
