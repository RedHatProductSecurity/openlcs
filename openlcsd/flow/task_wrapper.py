import celery
import os
import shutil


class WorkflowWrapperTask(celery.Task):

    abstract = True

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        """Handler called after the task returns."""
        if 'tmp_src_filepath' in args[0]:
            tmp_src_filepath = args[0].get('tmp_src_filepath')
            if tmp_src_filepath:
                tmp_dir = os.path.dirname(tmp_src_filepath)
                if os.path.exists(tmp_dir):
                    shutil.rmtree(tmp_dir, ignore_errors=True)

        if 'src_dest_dir' in args[0]:
            src_dir = args[0].get('src_dest_dir')
            if src_dir and os.path.exists(src_dir):
                shutil.rmtree(src_dir, ignore_errors=True)

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
