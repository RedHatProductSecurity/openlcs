
priority_str_kwargs_map = {
    "high": {},
    "medium": {"priority": 1, "queue": "celery:1"},
    "low": {"priority": 2, "queue": "celery:2"}
}

ALLOW_PRIORITY = list(priority_str_kwargs_map.keys())


class UnsupportedPriority(Exception):
    pass


def generate_priority_kwargs(priority: str) -> dict:
    """
    Generate celery task needed kwargs for specified priority.
    Priority can be one of the `high`, `medium`, `low`
    """
    if priority not in ALLOW_PRIORITY:
        raise UnsupportedPriority

    return priority_str_kwargs_map[priority]
