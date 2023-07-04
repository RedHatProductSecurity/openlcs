import ast
import configparser
import fcntl
import json
import os
import requests
import subprocess
from pathlib import Path
from requests.exceptions import RequestException, HTTPError

from openlcs.libs.constants import CONF_FILEPATH
from openlcs.libs.encrypt_decrypt import decrypt_with_secret_key


def get_config_file(config_file=Path(CONF_FILEPATH)):
    if config_file.is_file():
        return config_file
    # Attempt to find conf elsewhere
    dirname = Path(__file__).parent.absolute()
    config_file = dirname / 'conf.cfg'
    if config_file.is_file():
        return config_file
    return None


def load_config() -> configparser.ConfigParser:
    """Load configuration into a `ConfigParser` instance.

    Returns the config object or RuntimeError in case config file
    is not found or is not properly configured.
    """
    config_file = get_config_file()
    if not config_file:
        raise RuntimeError("Improperly configured, missing config file!")
    try:
        with open(config_file, "r", encoding="utf-8") as configfile:
            # An attempt to avoid race condition of multiple processes reading
            # the same configuration file concurrently. Not entirely sure if
            # it really helps, but I don't have a better idea.
            # See also: https://stackoverflow.com/a/34935188
            fcntl.flock(configfile, fcntl.LOCK_EX)
            config = configparser.ConfigParser(allow_no_value=True)
            config.read_file(configfile)
            fcntl.flock(configfile, fcntl.LOCK_UN)
    # ValueError means config file is not properly configured.
    except ValueError as e:
        raise RuntimeError(f"Error loading config: {e}") from None
    return config


def load_config_to_dict(section=None):
    """Load configuration into a dict.

    Returns a dictionary of config items in the specified section or
    an empty dict in case the section does not exist. IF no section is
    specified, a dict will be returned with keys as the section names
    and values as dict of config items in that section.
    """
    config = load_config()
    if section is None:
        return {s: dict(config.items(s)) for s in config.sections()}
    try:
        return dict(config.items(section))
    except configparser.NoSectionError:
        return {}


class OpenlcsClient:
    """
    Wrapper for communication with Hub, add authorization headers to
    all requests.
    """

    def __init__(self, task_id=None, parent_task_id=None, token=None):
        self.task_id = task_id
        self.parent_task_id = parent_task_id
        self.token = token
        self.token_sk = os.getenv("TOKEN_SECRET_KEY")
        self.config = load_config()
        self.api_url_prefix = self.get_api_url_prefix()
        self.session = requests.Session()
        self.headers = self.get_headers()

    def get_api_url_prefix(self):
        hub_server = self.config.get('general', 'hub_server')
        if hub_server == 'local':
            api_url_prefix = "http://{}:{}{}".format(
                self.config.get(hub_server, 'hostname'),
                self.config.get(hub_server, 'port'),
                self.config.get('general', 'api_path'),
            )
        else:
            api_url_prefix = "https://{}{}".format(
                self.config.get(hub_server, 'hostname'),
                self.config.get('general', 'api_path'),
            )
        return api_url_prefix

    def get_token_key(self):
        # For child tasks, use exist autobot user's token in the child tasks,
        # reduce get token frequency
        if all([self.token, self.token_sk, self.parent_task_id]):
            token_key = decrypt_with_secret_key(self.token, self.token_sk)
            return token_key

        # For parent task, get a local user token or autobot user token.
        # Get local user's token for the local environment.
        if self.config.get('general', 'hub_server') == 'local':
            token_obtain_url = 'obtain_token_local/'
            cmd = 'curl -sS -X POST -d "username={}&password={}" {}'.format(
                self.config.get('local', 'username'),
                self.config.get('local', 'password'),
                self.api_url_prefix + token_obtain_url
            )
        # Get autobot user's token from LDAP user's token for the OCP
        # environment.
        elif all([self.token, self.token_sk]):
            token = decrypt_with_secret_key(self.token, self.token_sk)
            cmd = 'curl -sS --negotiate -u : -H "{}" {}'.format(
                f'Authorization: Token {token}',
                self.api_url_prefix + 'get_autobot_token/'
            )
        else:
            err_msg = 'Failed to get token key.'
            raise RuntimeError(err_msg) from None

        try:
            output = subprocess.check_output(cmd, shell=True).decode('utf-8')
            token_key = ast.literal_eval(output).get('token')
        except (subprocess.CalledProcessError, AttributeError) as err:
            err_msg = f'Failed to get token key. Reason: {err}'
            raise RuntimeError(err_msg) from None
        return token_key

    def get_headers(self):
        token_key = self.get_token_key()
        return {
            'content-type': 'application/json',
            'Authorization': 'Token {}'.format(token_key)
        }

    def get_autobot_token(self, headers, params=None, timeout=300):
        url = "get_autobot_token"
        abs_url = self.get_abs_url(url)
        response = self.session.get(abs_url, headers=headers,
                                    params=params, timeout=timeout)
        token = response.json()
        return token

    def get_abs_url(self, url, sep="/"):
        # avoid recursive concatenations
        if self.api_url_prefix in url:
            return url
        return sep.join(s.strip(sep) for s in [self.api_url_prefix, url]) + sep

    def get(self, url, params=None, timeout=300):
        abs_url = self.get_abs_url(url)
        return self.session.get(abs_url, headers=self.headers,
                                params=params, timeout=timeout)

    def post(self, url, data, timeout=300):
        abs_url = self.get_abs_url(url)
        # http://stackoverflow.com/a/25895504
        # To resolve the issue that datetime.datetime object is not
        # JSON serializerable.

        def date_handler(obj):
            return obj.isoformat() if hasattr(obj, 'isoformat') else obj
        return self.session.post(
            abs_url, headers=self.headers, data=json.dumps(
                data, default=date_handler), timeout=timeout)

    def patch(self, url, data, timeout=300):
        abs_url = self.get_abs_url(url)
        # http://stackoverflow.com/a/25895504
        # To resolve the issue that datetime.datetime object is not
        # JSON serializerable.

        def date_handler(obj):
            return obj.isoformat() if hasattr(obj, 'isoformat') else obj
        return self.session.patch(
            abs_url, headers=self.headers, data=json.dumps(
                data, default=date_handler), timeout=timeout)

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
