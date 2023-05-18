import hashlib
import json
from redis import Redis
from redis_lock import Lock

from openlcsd.celeryconfig import broker_url


# Based upon singleton's lock generation mechanism with some simplification.
def generate_task_lock(
        task_name: str,
        task_args: list = [],
        task_kwargs: dict = {},
        task_identity_prefix: str = "TASK_IDENTICAL_LOCK_"
    ) -> str:
    """
    Generate a hash value for a task based on its name, args and kwargs.

    Args:
        name (str): Full name of the task.
        task_identity_prefix (str, optional): Prefix of the generated hash.
        args (list, optional): Arguments of the task.
        kwargs (dict, optional): Keyword arguments of the task.

    Returns:
        str: sha256 hash value with specified prefix, unique for each task
        with given signature.
    """
    str_args = json.dumps(task_args, sort_keys=True)
    str_kwargs = json.dumps(task_kwargs, sort_keys=True)
    task_repr = (task_name + str_args + str_kwargs).encode('utf-8')
    task_hash = hashlib.sha256(task_repr).hexdigest()
    return task_identity_prefix + task_hash


class RedisClient(object):

    def __init__(self) -> None:
        # FIXME: raise exception if `broker_url` is improperly configured
        self.client = Redis.from_url(broker_url)

    def get_lock(self, lock_key: str, lock_id=None):
        if lock_id is not None:
            return Lock(self.client, lock_key, id=lock_id)
        return Lock(self.client, lock_key)

    def release_lock_for_key(self, lock_key: str, lock_id=None) -> None:
        lock = self.get_lock(lock_key)
        # TODO: figure out why lock.release() won't work
        # lock.release()
        lock.reset()
