import os
from distutils.util import strtobool

DEBUG = True
TEMPLATE_DEBUG = True

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]

STATICFILES_STORAGE = (
    'django.contrib.staticfiles.storage.StaticFilesStorage'
)

TEST_EMAIL_TO = []
TEST_EMAIL_CC = []

DRF_NAMESPACE = 'rest'
DRF_API_VERSION = 'v1'
HOSTNAME = '127.0.0.1:8000'
REST_API_PATH = f'http://{HOSTNAME}/{DRF_NAMESPACE}/{DRF_API_VERSION}'

SRC_ROOT_DIR = '/tmp/cgit'
ADHOC_ARCHIVE_SRC_ROOT_DIR = os.path.join(SRC_ROOT_DIR, 'adhoc_storage')

LEGAL_LICENSE_USER_LIST = ['test_license']
LEGAL_EXPORT_USER_LIST = ['test_export']

LOGGER_DIR = 'logs'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': os.getenv('OLCS_TEST_DB_NAME', 'openlcs'),
        'USER': os.getenv('OLCS_TEST_DB_USER', 'postgres'),
        'PASSWORD': os.getenv('OLCS_TEST_DB_PASSWORD', 'test'),
        'HOST': os.getenv('OLCS_TEST_DB_HOST', 'postgres'),
        'PORT': os.getenv('OLCS_TEST_DB_PORT', '5432'),
    }
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'stderr': {
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stderr',
        }
    },
    'loggers': {
        '': {
            'level': 'INFO',
            'handlers': ['stderr'],
        },
        'django': {
            'propagate': True,
        },
        'django.db.backends': {
            'level': 'DEBUG',
            'handlers': ['stderr'],
        },
        'mozilla_django_oidc': {
            'handlers': ['stderr'],
            'level': 'DEBUG'
        },
    }
}

# Setting OIDC login and logout URLs.
OIDC_AUTH_URI = os.getenv("OIDC_AUTH_URI", "")
LOGIN_REDIRECT_URL = REST_API_PATH
LOGIN_REDIRECT_URL_FAILURE = REST_API_PATH
LOGOUT_REDIRECT_URL = OIDC_AUTH_URI + '/logout?redirect_uri=' + REST_API_PATH
