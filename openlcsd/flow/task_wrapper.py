import celery
import os
from commoncode.fileutils import delete

from openlcs.libs.redis import generate_task_lock


class WorkflowWrapperTask(celery.Task):

    abstract = True

    def _get_task_lock(self, task_args, task_kwargs):
        return generate_task_lock(self.name, task_args, task_kwargs)

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        """Handler called after the task returns."""
        from celery.contrib import rdb
        rdb.set_trace()
        task_lock = self._get_task_lock(args, kwargs)
        print(f"Task: {self.name}, args: {args}, lock: {task_lock}")
        if isinstance(args[0], dict):
            # Update the status of task when `duplicate_import` flag exists
            duplicate_import = args[0].get('duplicate_import')
            if status == 'SUCCESS' and duplicate_import:
                self.update_state(state='DUPLICATE')

            comp_type = args[0].get('component_type')
            # Only keep uncompressed sources for container
            if args[0].get('shared_remote_source'):
                pass
            elif comp_type != 'OCI' or args[0].get('parent'):
                src_dest_dir = args[0].get('src_dest_dir')
                if src_dest_dir and os.path.exists(src_dest_dir):
                    delete(src_dest_dir)
            # Only keep the source tarball for failed container components
            if status == 'FAILURE' and 'src_dir' in args[0]:
                pass
            elif args[0].get('shared_remote_source'):
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
