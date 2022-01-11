"""
Django settings for pelc2 project.

Generated by 'django-admin startproject' using Django 3.2.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.2/ref/settings/
"""
import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-8c4w#_a7k&1^!#+af%unwddrcc0=og^j7k@n*gjxm$^8b#tzdm'  # noqa

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = ['*']


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_filters',
    'rest_framework',
    'rest_framework.authtoken',
    'authentication',
    'packages',
    'products',
    'reports',
    'tasks',
    'utils'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'pelc.urls'

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
            ],
        },
    },
]

WSGI_APPLICATION = 'pelc.wsgi.application'


# Database
# https://docs.djangoproject.com/en/3.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'pelc2',
        'USER': os.environ.get('PELC_DATABASE_USER', 'pelc2'),
        'PASSWORD': os.environ.get('PELC_DATABASE_PASSWORD', ''),
        'HOST': '127.0.0.1',
        'PORT': '5432',
    }
}


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
STATIC_ROOT = '/var/pelc/static/'
STATICFILES_DIRS = (
    BASE_DIR / "static",
)

# Default primary key field type
# https://docs.djangoproject.com/en/3.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# celery broker settings
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_RESULT_BACKEND = 'db+postgresql://{USER}:{PASSWORD}@{HOST}/{NAME}'.format(**DATABASES.get('default'))    # noqa
CELERY_TASK_TRACK_STARTED = True
LOGGER_DIR = '/var/log/pelc/'

EXTRACTCODE_CLI = '/bin/extractcode'

# Brew settings
BREW_DOWNLOAD = 'http://download.eng.bos.redhat.com/brewroot'
BREW_WEBSERVICE = 'https://brewhub.engineering.redhat.com/brewhub'
BREW_WEBURL = 'https://brewweb.engineering.redhat.com/brew'

# Used to identify namespace for restful api endpoints.
DRF_NAMESPACE = 'rest'
DRF_API_VERSION = 'v1'

# Update the HOSTNAME to that of the running server
HOSTNAME = '127.0.0.1:8000'
BROWSABLE_DOCUMENT_MACROS = {
    'HOST_NAME': 'http://%s' % (HOSTNAME),
    'API_PATH': '%s/%s' % (DRF_NAMESPACE, DRF_API_VERSION),
}


REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
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

# Bulk create settings
CREATE_FILES_RAND = True
CREATE_FILES_MAX_RETRIES = 5
CREATE_FILES_MAX_WAIT_INTERVAL = 10
CREATE_PATHS_RAND = True
CREATE_PATHS_MAX_RETRIES = 5
CREATE_PATHS_MAX_WAIT_INTERVAL = 10

try:
    # pylint:disable=wildcard-import,unused-wildcard-import
    from .settings_local import *  # noqa
except ImportError:
    pass
