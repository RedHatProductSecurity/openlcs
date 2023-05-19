import hashlib
import json
from redis import Redis
from redis_lock import Lock

from openlcsd.celeryconfig import broker_url
from openlcsd.celeryconfig import task_time_limit
from .constants import TASK_IDENTITY_PREFIX  # noqa: E402


# Based upon singleton's lock generation mechanism with some simplification.
def generate_lock_key(
        task_name: str,
        task_args: list = None,
        task_kwargs: dict = None,
        task_identity_prefix: str = TASK_IDENTITY_PREFIX
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
    if task_args is None:
        task_args = list()
    if task_kwargs is None:
        task_kwargs = dict()
    str_args = json.dumps(task_args, sort_keys=True)
    str_kwargs = json.dumps(task_kwargs, sort_keys=True)
    task_repr = (task_name + str_args + str_kwargs).encode('utf-8')
    task_hash = hashlib.sha256(task_repr).hexdigest()
    return task_identity_prefix + task_hash


class RedisClient(object):

    def __init__(self) -> None:
        # FIXME: raise exception if `broker_url` is improperly configured
        self.client = Redis.from_url(broker_url)

    def get_lock(self, lock_key: str, lock_id=None,
                 expire: int = task_time_limit):
        """Retrieve a lock object based on the provided lock_key and
        optional lock_id.

        Args:
            lock_key (str): The key associated with the lock.
            lock_id (str, optional): The unique identifier for the lock.
                Defaults to None.
            expire (int, optional): The expiration time for the lock in
                seconds. Defaults to task_time_limit.

        Returns:
            redis_lock.Lock: A lock object with the provided parameters.
        """
        if lock_id is not None:
            return Lock(self.client, lock_key, id=lock_id, expire=expire)
        return Lock(self.client, lock_key, expire=expire)

    def release_lock_for_key(self, lock_key: str, lock_id=None) -> None:
        """Release a lock specified by lock_key and optionally lock_id.

        Args:
            lock_key (str): key needed to initialize the lock
            lock_id (str, optional): id attribute of the lock object. Useful
                when you want to release the lock in a different place other
                than where the lock is acquired. Defaults to None.
        """
        lock = self.get_lock(lock_key)
        # FIXME: Forcibly deletes the lock. Need to figure out why
        # lock.release() won't work.
        lock.reset()
