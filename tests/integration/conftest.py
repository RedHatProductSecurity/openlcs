import os
import pytest
import requests
import sys
import time
from urllib.parse import urlparse
from requests_kerberos import HTTPKerberosAuth
from datetime import datetime, timedelta
from os.path import join, pardir, dirname, normpath

from django.conf import settings
from django.core.management import call_command

TESTDIR = dirname(__file__)
TOPDIR = normpath(join(TESTDIR, pardir, pardir))
OPENLCSDIR = join(TOPDIR, 'openlcs')



def pytest_configure():
    sys.path = [OPENLCSDIR, TOPDIR] + sys.path
    settings_path = join(OPENLCSDIR, 'openlcs', 'settings.py')


#OPENLCS_URL = os.environ.get('OPENLCS_TEST_URL')
OPENLCS_URL = "https://openlcs-ci.apps.int.spoke.preprod.us-west-2.aws.paas.redhat.com/"
OPENLCS_LOCAL_LOGIN = os.environ.get('OPENLCS_TEST_LOCAL')
if not OPENLCS_URL:
    OPENLCS_URL = 'http://localhost:8000'
    OPENLCS_LOCAL_LOGIN = True
OPENLCS_URL = OPENLCS_URL.rstrip('/')
OPENLCS_LOGIN_DATA = {
    'username': os.environ.get('OPENLCS_TEST_USER', 'admin'),
    'password': os.environ.get('OPENLCS_TEST_PASS', 'test'),
}


class OpenLCSTestClient(object):
    def __init__(self):
        self.session = requests.Session()
        self._token = None
        self.csrf_token = None

    def request(self, endpoint, method='GET', headers=None, auth='default',
                expected_code=200, **kwargs):
        headers = dict(headers or {})
        if self.csrf_token:
            headers['X-CSRFToken'] = self.csrf_token
        if auth == 'token':
            headers['Authorization'] = 'token {}'.format(self.get_token())
        elif auth == 'default':
            if OPENLCS_LOCAL_LOGIN and 'sessionid' not in self.session.cookies:
                # Obtain CSRF token
                self.request('/', auth=None)
                self.request(
                    '/login/',
                    method='POST',
                    data=OPENLCS_LOGIN_DATA,
                    auth=None,
                )
            else:
                kwargs['auth'] = HTTPKerberosAuth(mutual_authentication=False)
        elif auth is None:
            # No auth
            pass
        else:
            assert False, "Unknown auth type"
        if not urlparse(endpoint).netloc:
            endpoint = '{}/{}'.format(OPENLCS_URL, endpoint.lstrip('/'))
        self.assert_url_same_host(endpoint)
        response = self.session.request(
            method,
            endpoint,
            headers=headers,
            **kwargs
        )
        self.csrf_token = self.session.cookies.get(
            'csrftoken',
            default=self.csrf_token,
        )
        # requests internally add some headers, we don't want them in curlify
        # output
        response.request.headers = headers
        print(self.to_curl(response.request))
        assert not expected_code or response.status_code == expected_code, (
            "Request returned status {}, expected {}\nResponse body:\n{}"
            .format(response.status_code, expected_code, response.content)
        )
        return response

    def to_curl(self, request):
        if request.body and request.body.startswith('--'):
            # It would choke on binary input
            request.body = 'XXX Multipart content omitted'
        try:
            import curlify
            return curlify.to_curl(request)
        except ImportError:
            return "To see curl command invocation, please install curlify"

    def api_call(self, endpoint, method='GET', headers=None, return_json=True,
                 expected_code=200, **kwargs):
        if not urlparse(endpoint).netloc:
            endpoint = 'rest/v1/{}'.format(endpoint.lstrip('/'))
        headers = dict(headers or {})
        headers['Accept'] = 'application/json'
        response = self.request(
            endpoint=endpoint,
            method=method,
            headers=headers,
            auth='token',
            expected_code=expected_code,
            **kwargs
        )
        if not return_json:
            return response
        assert response.headers.get('Content-Type') == 'application/json', \
            "API call didn't return json Content-Type"
        return response.json()

    def get_token(self):
        if self._token:
            return self._token
        if OPENLCS_LOCAL_LOGIN:
            response = self.request(
                '/rest/v1/obtain_token_local/',
                method='POST',
                data=OPENLCS_LOGIN_DATA,
                auth=None,
            )
        else:
            response = self.request('/rest/v1/auth/obtain_token/')
        assert response.status_code == 200, \
            "Login returned status {}: {}"\
            .format(response.status_code, response.content)
        assert response.headers.get('Content-Type') == 'application/json', \
            "Login didn't return json Content-Type"
        self._token = response.json()['token']
        return self._token

    def assert_url_same_host(self, url):
        assert urlparse(OPENLCS_URL).netloc == urlparse(url).netloc

    def update_crontab_schedule(self):
        now = datetime.now()
        future_time = now + timedelta(seconds=5)
        print(now)
        print(future_time)
        schedule, _ = CrontabSchedule.objects.get_or_create(
            minute=future_time.minute,
            hour=future_time.hour,
            day_of_week='*',
            day_of_month='*',
            month_of_year='*',
            )
        print(PeriodicTask.objects.all())
        run_corgi_sync = PeriodicTask.objects.get(name='run_corgi_sync')
        run_corgi_sync.crontab = schedule
        run_corgi_sync.save()


@pytest.fixture()
def django_db_setup():
    settings.DATABASES['openlcs'] = {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'openlcs',
        'USER': os.environ.get('OPENLCS_DATABASE_USER', 'openlcs'),
        'PASSWORD': os.environ.get('OPENLCS_DATABASE_PASSWORD', ''),
        'HOST': os.environ.get('OPENLCS_DATABASE_HOST', '127.0.0.1'),
        'PORT': '5432',
    }


@pytest.fixture
def client():
    return OpenLCSTestClient()
