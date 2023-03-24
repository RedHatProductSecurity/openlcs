import os
import json
import requests
from requests.exceptions import RequestException, HTTPError
import configparser
import subprocess
import ast
from openlcs.libs.encrypt_decrypt import decrypt_with_secret_key
from krbcontext import krbcontext

if os.path.isfile('/etc/openlcs/openlcslib.conf'):
    config_file = '/etc/openlcs/openlcslib.conf'
else:
    dirname = os.path.abspath(os.path.dirname(__file__))
    config_file = os.path.join(dirname, 'conf.cfg')


class OpenlcsClient(object):
    """
    Wrapper for communication with Hub, add authorization headers to
    all requests.
    """

    def __init__(self, task_id=None, token=None, token_sk=None):
        self.session = requests.Session()
        config = configparser.ConfigParser(os.environ, allow_no_value=True)
        try:
            with open(config_file, encoding='utf8') as configfile:
                config.read_file(configfile)
        except FileNotFoundError as err:
            err_msg = f'Failed to read configure file. Reason: {err}'
            raise RuntimeError(err_msg) from None
        hub_server = config.get('general', 'hub_server')
        keytab_file = config.get('general', 'keytab_file')
        svc_principal_hostname = config.get('general',
                                            'service_principal_hostname')
        principal = f"{svc_principal_hostname}@IPA.REDHAT.COM"

        # use exist token, reduce get token frequency
        if token is not None and token_sk is not None:
            if hub_server == 'local':
                self.api_url_prefix = "http://{}:{}{}".format(
                    config.get(hub_server, 'hostname'),
                    config.get(hub_server, 'port'),
                    config.get('general', 'api_path'),
                )
            else:
                self.api_url_prefix = "https://{}{}".format(
                    config.get(hub_server, 'hostname'),
                    config.get('general', 'api_path'),
                )

            self.headers = {
                'content-type': 'application/json',
                'Authorization': 'Token {}'.format(
                    decrypt_with_secret_key(token, token_sk)
                )
            }
            self.task_id = task_id
            return

        # Construct api_url_prefix and cmd
        if hub_server == 'local':
            self.api_url_prefix = "http://{}:{}{}".format(
                config.get(hub_server, 'hostname'),
                config.get(hub_server, 'port'),
                config.get('general', 'api_path'),
                )
            token_obtain_url = 'obtain_token_local/'
            cmd = 'curl -sS -X POST -d "username={}&password={}" {}'.format(
                config.get('local', 'username'),
                config.get('local', 'password'),
                self.api_url_prefix+token_obtain_url
                )
            output = subprocess.check_output(cmd, shell=True).decode('utf-8')
        else:
            # self.config['hostname'] = conf.get(hub_server, 'hostname')
            self.api_url_prefix = "https://{}{}".format(
                config.get(hub_server, 'hostname'),
                config.get('general', 'api_path'),
            )
            token_obtain_url = 'auth/obtain_token/'
            with krbcontext(using_keytab=True,
                            principal=principal,
                            ccache_file='/tmp/openlcs_ccache',
                            keytab_file=keytab_file):
                cmd = [
                    'curl', '-sS', '--negotiate', '-u', ':',
                    self.api_url_prefix + token_obtain_url,
                ]
                output = subprocess.check_output(cmd).decode('utf-8')
        try:
            token_key = ast.literal_eval(output).get('token')
        except AttributeError as err:
            err_msg = f'Failed to get token key. Reason: {err}'
            raise RuntimeError(err_msg) from None
        self.headers = {
            'content-type': 'application/json',
            'Authorization': 'Token {}'.format(token_key)
        }
        self.task_id = task_id

    def get_abs_url(self, url, sep="/"):
        # avoid recursive concatenations
        if self.api_url_prefix in url:
            return url
        return sep.join(s.strip(sep) for s in [self.api_url_prefix, url]) + sep

    def get(self, url, params=None):
        abs_url = self.get_abs_url(url)
        return self.session.get(abs_url, headers=self.headers,
                                params=params, timeout=10)

    def get_paginated_data(self, url, query_params=None):
        """
        Retrieves paginated data from `url`.

        The implementation assumes that the API endpoint returns paginated
        data with following form:
        {
            "previous": url of the previous page (if any),
            "next": url of the next page (if any),
            "results": a list of data
        }

        :param url: the path of the API endpoint
        :param query_params: a dictionary of query parameters.
        :return: yields each page of data as a list
        """
        while url:
            try:
                response = self.get(url, params=query_params)
                response.raise_for_status()
                data = response.json()
                yield from data["results"]
                url = data.get("next")
                if query_params:
                    query_params = None
            except (HTTPError, RequestException):
                # FIXME: fail silently is not ideal
                break

    def post(self, url, data, timeout=10):
        abs_url = self.get_abs_url(url)
        # http://stackoverflow.com/a/25895504
        # To resolve the issue that datetime.datetime object is not
        # JSON serializerable.

        def date_handler(obj):
            return obj.isoformat() if hasattr(obj, 'isoformat') else obj
        return self.session.post(
            abs_url, headers=self.headers, data=json.dumps(
                data, default=date_handler), timeout=timeout)

    def patch(self, url, data):
        abs_url = self.get_abs_url(url)
        # http://stackoverflow.com/a/25895504
        # To resolve the issue that datetime.datetime object is not
        # JSON serializerable.

        def date_handler(obj):
            return obj.isoformat() if hasattr(obj, 'isoformat') else obj
        return self.session.patch(
            abs_url, headers=self.headers, data=json.dumps(
                data, default=date_handler), timeout=10)
