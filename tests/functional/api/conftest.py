from os.path import join, pardir, dirname, normpath
from urllib.parse import urlparse

import pytest
import requests
from django.core.management import call_command

TESTDIR = dirname(__file__)
TOPDIR = normpath(join(TESTDIR, pardir, pardir, pardir))
OPENLCSDIR = join(TOPDIR, 'openlcs')


class OpenlcsTestClient:

    # test user and password must be the same as defined in database_data.json
    # which is used for populating database
    test_user = 'admin'
    test_pass = 'test'

    USER_AGENT = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux i686; rv:64.0) '
                      'Gecko/20100101 Firefox/64.0'
    }

    def __init__(self, url, user=None, password=None):
        self.url = url.rstrip('/')
        self.token = None

        if user:
            self.test_user = user
        if password:
            self.test_pass = password

    def request(self, endpoint, method='GET', headers=None, **kwargs):
        headers = dict(headers or {})
        if self.token:
            headers['Authorization'] = 'token {}'.format(self.token)
        if not urlparse(endpoint).netloc:
            endpoint = '{}/{}'.format(self.url, endpoint.lstrip('/'))
            if not urlparse(endpoint).query:
                endpoint += '?ordering=id'
            else:
                url, query = endpoint.split('?', 1)
                endpoint = url + '?ordering=id&' + query
        self.assert_url_same_host(endpoint)
        response = requests.request(
            method,
            endpoint,
            headers=headers,
            **kwargs
        )
        # requests internally add some headers, we don't want them in curlify
        # output
        response.request.headers = headers
        print(self.to_curl(response.request))
        return response

    def to_curl(self, request):
        try:
            import curlify
            return curlify.to_curl(request)
        except ImportError:
            return "To see curl command invocation, please install curlify"

    def api_call(self, endpoint, method='GET', headers=None, return_json=True,
                 expected_code=200, fake_browser=False, **kwargs):
        # List of methods can be updated if methods is missing
        assert method in ['GET', 'POST', 'PATCH', 'PUT'], \
            "Unknown request method '{}'".format(method)

        if not urlparse(endpoint).netloc:
            endpoint = 'rest/v1/{}'.format(endpoint.lstrip('/'))
        headers = dict(headers or {})
        if fake_browser:
            headers.update(self.USER_AGENT)
        headers['Accept'] = 'application/json'
        response = self.request(
            endpoint=endpoint,
            method=method,
            headers=headers,
            **kwargs
        )
        assert response.status_code == expected_code, \
            "API call returned status {}\nResponse body:\n{}" \
            .format(response.status_code, response.content)
        if not return_json:
            return response
        assert response.headers.get('Content-Type') == 'application/json', \
            "API call didn't return json Content-Type"
        return response.json()

    def get_token(self):
        request_url = '{}/{}'.format(
            self.url, 'rest/v1/obtain_token_local/')
        response = requests.post(
            request_url,
            data={"username": self.test_user, "password": self.test_pass}
        )
        assert response.status_code == 200, \
            "Login returned status {}: {}"\
            .format(response.status_code, response.content)
        assert response.headers.get('Content-Type') == 'application/json', \
            "Login didn't return json Content-Type"
        return response.json()['token']

    def login(self):
        self.token = self.get_token()

    def assert_url_same_host(self, url):
        assert urlparse(self.url).netloc == urlparse(url).netloc


@pytest.fixture
def openlcs_client(live_server, openlcs_setup):
    openlcs_client = OpenlcsTestClient(live_server.url)
    openlcs_client.login()
    return openlcs_client


@pytest.fixture
def openlcs_client_unprivileged(django_db_setup, live_server, openlcs_setup):
    openlcs_client = OpenlcsTestClient(
        live_server.url, 'test_privileges', 'privileges')
    openlcs_client.login()
    return openlcs_client

