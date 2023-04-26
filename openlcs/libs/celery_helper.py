from .exceptions import UnsupportedPriority
from .constants import (
    PRIORITY_STR_KWARGS_MAP,
    ALLOW_PRIORITY
)


def generate_priority_kwargs(priority: str) -> dict:
    """
    Generate celery task needed kwargs for specified priority.
    Priority can be one of the `high`, `medium`, `low`
    """
    if priority not in ALLOW_PRIORITY:
        raise UnsupportedPriority

    return PRIORITY_STR_KWARGS_MAP[priority]
