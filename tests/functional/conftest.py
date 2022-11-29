import sys
from os.path import join, pardir, dirname, normpath

import pytest
from django.conf import settings
from django.core.management import call_command
from django.db import connection

TESTDIR = dirname(__file__)
TOPDIR = normpath(join(TESTDIR, pardir, pardir))
OPENLCSDIR = join(TOPDIR, 'openlcs')

TEST_USER = 'admin'
TEST_PASS = 'test'


def pytest_configure():
    sys.path = [OPENLCSDIR, TOPDIR] + sys.path
    settings_path = join(OPENLCSDIR, 'openlcs', 'settings.py')

    # Override settings_local from the pel repo with ours
    conf_vars = {'__file__': ''}
    with open(settings_path) as settings_file:
        old_path = sys.path
        # Settings also need to access third-party module we installed.
        # Add python related path to sys.path avoiding ModuleNotFoundError
        sys.path = [TESTDIR] + [p for p in old_path if 'python' in p]
        try:
            output = "\n".join(settings_file.readlines())
            exec(output, conf_vars)
        finally:
            sys.path = old_path

    del conf_vars['__file__']
    del conf_vars['__builtins__']
    del conf_vars['__doc__']
    del conf_vars['os']
    del conf_vars['Path']
    del conf_vars['sys']
    del conf_vars['parent_dir']
    del conf_vars['Fernet']
    settings.configure(**conf_vars)


@pytest.fixture(scope='session')
def openlcs_setup(redis_nooproc):
    settings.CELERY_BROKER_URL = \
        'redis://{r.host}:{r.port}/0'.format(r=redis_nooproc)
    db_params = connection.settings_dict
    settings.CELERY_RESULT_BACKEND = (
        'db+postgresql://{USER}@{HOST}/{NAME}'.format(**db_params)
    )


@pytest.fixture()
def django_db_setup(django_db_setup, django_db_blocker):
    # Note: Look at README.md how to properly create the database dump
    with django_db_blocker.unblock():
        # make sure celery meta tables exist before loaddata
        with connection.cursor() as cursor:
            cursor.execute(open(join(TESTDIR, "celery_meta.sql"), "r").read())
        call_command(
            'loaddata',
            join(dirname(__file__), 'database_data.json'))
