"""
Django settings for OpenLCS project.

Generated by 'django-admin startproject' using Django 3.2.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.2/ref/settings/
"""
import os
import sys
from pathlib import Path

from celery.schedules import crontab
from cryptography.fernet import Fernet
# from datetime import timedelta

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-8c4w#_a7k&1^!#+af%unwddrcc0=og^j7k@n*gjxm$^8b#tzdm'  # noqa

# secret key for auth token encrypt and decrypt
TOKEN_SECRET_KEY = Fernet.generate_key().decode()

# SECURITY WARNING: don't run with debug turned on in production!
# This value will be overwritten in production configuration
DEBUG = True

ALLOWED_HOSTS = ['*']


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_celery_beat',
    'django_filters',
    "debug_toolbar",
    'rest_framework',
    'rest_framework.authtoken',
    'authentication',
    'packages',
    'products',
    'reports',
    'tasks',
    'utils',
    'mptt',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    "debug_toolbar.middleware.DebugToolbarMiddleware",
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'authentication.middleware.RemoteUserMiddleware',
]

ROOT_URLCONF = 'openlcs.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'debug': DEBUG,
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'utils.context_processors.get_app_version',
            ],
        },
    },
]

WSGI_APPLICATION = 'openlcs.wsgi.application'


# Database
# https://docs.djangoproject.com/en/3.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'openlcs',
        'USER': os.environ.get('OPENLCS_DATABASE_USER', 'openlcs'),
        'PASSWORD': os.environ.get('OPENLCS_DATABASE_PASSWORD', ''),
        'HOST': os.environ.get('OPENLCS_DATABASE_HOST', '127.0.0.1'),
        'PORT': '5432',
    }
}

REST_FRAMEWORK_EXTENSIONS = {
    'DEFAULT_CACHE_RESPONSE_TIMEOUT': 60 * 10,
    'DEFAULT_USE_CACHE': 'default'
}

RELEASE_LIST_CACHE_TIMEOUT = 60 * 60

RELEASE_RETRIEVE_CACHE_TIMEOUT = 60 * 15

# Password validation
# https://docs.djangoproject.com/en/3.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',  # noqa
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',  # noqa
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',  # noqa
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',  # noqa
    },
]


# Internationalization
# https://docs.djangoproject.com/en/3.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.2/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = '/srv/git/repos/openlcs/static/'
STATICFILES_DIRS = (
    BASE_DIR / "static",
)

# Default primary key field type
# https://docs.djangoproject.com/en/3.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# celery broker settings
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL',
                                   'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_RESULT_BACKEND = 'db+postgresql://{USER}:{PASSWORD}@{HOST}/{NAME}'.format(**DATABASES.get('default'))    # noqa
CELERY_TASK_TRACK_STARTED = True
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_BEAT_SCHEDULE = {
    # Refer to https://docs.celeryq.dev/en/v5.2.7/userguide/periodic-tasks.html#periodic-tasks  # noqa
    'run_corgi_sync': {
        'task': 'openlcsd.flow.periodic_tasks.run_corgi_sync',
        'schedule': crontab(minute=0, hour=0),  # Execute daily at midnight.
        'kwargs': {'provenance': 'sync_corgi'}
    },
    'clean_unused_shared_remote_source': {
        'task': 'openlcsd.flow.periodic_tasks.'
                'clean_unused_shared_remote_source',
        'schedule': crontab(minute=0, hour=0),
    }
}
# https://docs.celeryq.dev/en/v5.2.7/userguide/routing.html#redis-message-priorities
CELERY_BROKER_TRANSPORT_OPTIONS = {
    'visibility_timeout': 86400,
    'priority_steps': [0, 1, 2],
    'sep': ':',
    'queue_order_strategy': 'priority',
}

LOGGER_DIR = '/var/log/openlcs/'

# Scancode settings
SCANCODE_LICENSE_SCORE = 20
SCANCODE_PROCESSES = 1
SCANCODE_TIMEOUT = 300
# Update below path to your virtualenv path in local
SCANCODE_CLI = '/opt/app-root/bin/scancode'
EXTRACTCODE_CLI = '/opt/app-root/bin/extractcode'

# Brew/Koji settings
KOJI_DOWNLOAD = os.getenv(
    'KOJI_DOWNLOAD',
    'https://kojipkgs.fedoraproject.org')
KOJI_WEBSERVICE = os.getenv(
    'KOJI_WEBSERVICE',
    'https://koji.fedoraproject.org/kojihub')
KOJI_WEBURL = os.getenv(
    'KOJI_WEBURL',
    'https://koji.fedoraproject.org/koji/index')

# Used to identify namespace for restful api endpoints.
DRF_NAMESPACE = 'rest'
DRF_API_VERSION = 'v1'

# Update the HOSTNAME to that of the running server
HOSTNAME = '127.0.0.1:8000'
REST_API_PATH = f'http://{HOSTNAME}/{DRF_NAMESPACE}/{DRF_API_VERSION}'
BROWSABLE_DOCUMENT_MACROS = {
    # need to be rewritten with the real host name when deploy.
    'HOST_NAME': f'http://{HOSTNAME}',
    # make consistent with rest api root.
    'API_PATH': f'{DRF_NAMESPACE}/{DRF_API_VERSION}',
}

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'PAGE_SIZE': 20,
    'DEFAULT_PAGINATION_CLASS':
        'rest_framework.pagination.LimitOffsetPagination',
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
    ),
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
        'utils.renderers.ReadOnlyBrowsableAPIRenderer',
    ),
}

# Bulk create retry settings
SAVE_DATA_MAX_RETRIES = 5

# Directory where the source code will be hosted. Note that
# appropriate permission(r+w) / secontext is needed.
SRC_ROOT_DIR = '/srv/git/repos/openlcs'

# The root directory for remote source package source tarball import
RS_SRC_ROOT_DIR = os.path.join(SRC_ROOT_DIR, 'remote_source')
RS_TYPES = ['GOLANG', 'NPM', 'YARN', 'PYPI', 'CARGO', 'GEM']

# The root directory for package source tarball for package import retry
RETRY_DIR = os.path.join(SRC_ROOT_DIR, 'retry')

# The root directory for temporary package source tarball for package import
TMP_ROOT_DIR = os.path.join(SRC_ROOT_DIR, 'tmp')

# The root directory for post/adhoc post data file for package import
POST_DIR = os.path.join(SRC_ROOT_DIR, 'post')

# 'orphan' category will be used if product release is not specified
ORPHAN_CATEGORY = 'orphan'

# Ldap settings
LDAP_URI = os.getenv("LDAP_URI")
LDAP_USERS_DN = "ou=users,dc=redhat,dc=com"

# Email REALM
EMAIL_REALM = 'REDHAT.COM'

# Give superuser permission to these users.
OPENLCS_ADMIN_LIST = [
    'jzhao', 'yuwang', 'huiwang', 'qduanmu', 'yulwang', 'chhan', 'axuan',
    'openlcs-dev-worker01', 'openlcs-qe-worker01', 'openlcs-ci-worker01',
    'openlcs-stage-worker01', 'openlcs-prod-worker01', 'openlcs'
]

# CSRF setting
# https://docs.djangoproject.com/zh-hans/3.2/ref/settings/#csrf-cookie-domain
# CSRF_COOKIE_DOMAIN = ['.redhat.com', '127.0.0.1']
CSRF_COOKIE_DOMAIN = '127.0.0.1'


# Corgi setting
CORGI_API_STAGE = os.getenv("CORGI_API_STAGE", "")
CORGI_API_PROD = os.getenv("CORGI_API_PROD", "")
# https://github.com/RedHatProductSecurity/component-registry/blob/main/corgi/core/models.py#L721    # noqa
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

# cache location settings
REDIS_CACHE_LOCATION = os.environ.get('REDIS_CACHE_LOCATION',
                                      'redis://localhost:6379/1')

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_CACHE_LOCATION,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {"max_connections": 100}
        },
    },
}

try:
    # pylint:disable=wildcard-import,unused-wildcard-import
    parent_dir = os.path.abspath(os.path.dirname(__file__))
    if parent_dir not in sys.path:
        sys.path.append(parent_dir)
    from settings_local import *  # noqa
except ImportError:
    pass
