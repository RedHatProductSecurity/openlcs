import sys
from os.path import join, pardir, dirname, normpath

import pytest
from django.conf import settings
from django.core.management import call_command
from django.db import connection

TESTDIR = dirname(__file__)
TOPDIR = normpath(join(TESTDIR, pardir, pardir))
PELCDIR = join(TOPDIR, 'pelc')

TEST_USER = 'admin'
TEST_PASS = 'test'


def pytest_configure():
    sys.path = [PELCDIR, TOPDIR] + sys.path
    settings_path = join(PELCDIR, 'pelc', 'settings.py')

    # Override settings_local from the pel repo with ours
    conf_vars = {'__file__': ''}
    with open(settings_path) as settings_file:
        old_path = sys.path
        sys.path = [TESTDIR]
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
    settings.configure(**conf_vars)


@pytest.fixture(scope='session')
def pelc_setup(redis_nooproc):
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
        call_command(
            'loaddata',
            join(dirname(__file__), 'database_data.json'))