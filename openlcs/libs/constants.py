CONF_FILEPATH = "/etc/openlcs/openlcslib.conf"

# Celery task priority/queue setup.
PRIORITY_STR_KWARGS_MAP = {
    "high": {},
    "medium": {"priority": 1, "queue": "celery:1"},
    "low": {"priority": 2, "queue": "celery:2"}
}

ALLOW_PRIORITY = list(PRIORITY_STR_KWARGS_MAP.keys())
TASK_IDENTITY_PREFIX = "TASK_IDENTICAL_LOCK_"
