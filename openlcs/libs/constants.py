CONF_FILEPATH = "/etc/openlcs/openlcslib.conf"

# Celery task priority/queue setup
PRIORITY_STR_KWARGS_MAP = {
    "high": {},
    "medium": {"priority": 1, "queue": "celery:1"},
    "low": {"priority": 2, "queue": "celery:2"}
}

ALLOW_PRIORITY = list(PRIORITY_STR_KWARGS_MAP.keys())
TASK_IDENTITY_PREFIX = "TASK_IDENTICAL_LOCK_"

# Request timeout
DEFAULT_REQUEST_TIMEOUT = 300
EXTENDED_REQUEST_TIMEOUT = 600

# Corgi component
CORGI_COMPONENT_TYPES = [
    "CARGO",
    "OCI",
    "GEM",
    "GENERIC",
    "GITHUB",
    "GOLANG",
    "MAVEN",
    "NPM",
    "RPMMOD",
    "RPM",
    "PYPI"
]
PARENT_COMPONENT_TYPES = ['OCI', 'RPMMOD']
RS_TYPES = ['GOLANG', 'NPM', 'YARN', 'PYPI', 'CARGO', 'GEM']
