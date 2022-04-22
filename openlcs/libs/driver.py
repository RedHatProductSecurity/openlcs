import os
import json
import requests
import configparser
import subprocess
import ast


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

    def __init__(self, task_id=None):
        config = configparser.ConfigParser(allow_no_value=True)
        try:
            with open(config_file, encoding='utf8') as configfile:
                config.read_file(configfile)
        except FileNotFoundError as err:
            err_msg = f'Failed to read configure file. Reason: {err}'
            raise RuntimeError(err_msg) from None
        hub_server = config.get('general', 'hub_server')

        # Construct api_url_prefix and cmd
        output = None
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

    def get_abs_url(self, url):
        sep = "/"
        return sep.join(s.strip(sep) for s in [self.api_url_prefix, url]) + sep

    def get(self, url, params=None):
        abs_url = self.get_abs_url(url)
        return requests.get(abs_url, headers=self.headers, params=params)

    def post(self, url, data):
        abs_url = self.get_abs_url(url)
        # http://stackoverflow.com/a/25895504
        # To resolve the issue that datetime.datetime object is not
        # JSON serializerable.

        def date_handler(obj):
            return obj.isoformat() if hasattr(obj, 'isoformat') else obj
        return requests.post(
            abs_url, headers=self.headers, data=json.dumps(
                data, default=date_handler))

    def patch(self, url, data):
        abs_url = self.get_abs_url(url)
        # http://stackoverflow.com/a/25895504
        # To resolve the issue that datetime.datetime object is not
        # JSON serializerable.

        def date_handler(obj):
            return obj.isoformat() if hasattr(obj, 'isoformat') else obj
        return requests.patch(
            abs_url, headers=self.headers, data=json.dumps(
                data, default=date_handler))
