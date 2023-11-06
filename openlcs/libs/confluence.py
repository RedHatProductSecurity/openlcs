import functools
import hashlib
import logging
import requests
import time
import urllib.parse
import urllib3.util.retry

from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)

_adapter = requests.adapters.HTTPAdapter(
    max_retries=urllib3.util.retry.Retry(
        total=15,
        status_forcelist=[429, 500, 502, 503, 504],
        # Deprecated, removed in v2.0
        # method_whitelist=["HEAD", "GET", "OPTIONS"],
        backoff_factor=1,
    )
)
_session = requests.Session()
_session.mount("https://", _adapter)


def retry(timeout=180, interval=5, wait_on=Exception):
    """
    A decorator that allows to retry a section of code until success
    or timeout.
    """
    def wrapper(function):
        @functools.wraps(function)
        def inner(*args, **kwargs):
            start = time.time()
            while True:
                try:
                    return function(*args, **kwargs)
                except wait_on:
                    time.sleep(interval)
                    if (time.time() - start) >= timeout:
                        raise  # This re-raises the last exception.
        return inner

    return wrapper


class BearerAuth(requests.auth.AuthBase):
    def __init__(self, token):
        self.token = token

    def __call__(self, r):
        r.headers["authorization"] = "Bearer " + self.token
        return r


class ConfluenceClient:
    """
    A conflence client used to connect to confluence and perform confluence
    related tasks.
    """

    def __init__(
        self,
        confluence_url,
        username=None,
        password=None,
        token=None,
        auth_type="basic",
    ):
        """
        Returns confluence client object.
        :param string confluence_url : url to connect confluence
        :param string username : optional username for basic auth
        :param string password : optional password for basic auth
        :param string auth_type : auth scheme, basic and token are supported
        """
        self.confluence_url = confluence_url
        self.confluence_rest_url = self.confluence_url + "/rest/api/content/"
        self.username = username
        self.password = password
        self.token = token
        self.authtype = auth_type
        self._req_kwargs = None

    @property
    def req_kwargs(self):
        """
        Set the key-word arguments for python-requests depending on the auth
        type. This code should run on demand exactly once, which is why it is
        a property.
        :return dict _req_kwargs: dict with the right options to pass in
        """
        if self._req_kwargs is None:
            if self.authtype in ['basic', 'token']:
                self._req_kwargs = {'auth': self.get_auth_object()}
        return self._req_kwargs

    def find_page(self, space, page_title):
        """
        Find the page with title page_title in space
        :param string space : space to be used in confluence
        :param string page_title : Title of page to be created in confluence
        :return json conf_resp: response from the confluence
        """
        cql = "title='" + page_title + "' and " + "space='" + space + "'"
        search_url = (
            self.confluence_url
            + "/rest/api/content/search?"
            + urllib.parse.urlencode({'cql': cql})
        )
        resp = _session.get(search_url, **self.req_kwargs)
        resp.raise_for_status()
        if len(resp.json()['results']) > 0:
            return resp.json()['results'][0]
        else:
            logger.debug("Confluence response: %s", resp.text)
            return None

    @retry(timeout=10, interval=3, wait_on=TypeError)
    def retry_find_page(self, space, page_title):
        """
        Retry find_page if page is not immediately returned.
        :param string space : space to be used in confluence
        :param string page_title : Title of page to be created in confluence
        :return page: response from confluence
        """
        page = self.find_page(space, page_title)
        if not page:
            raise TypeError("Invalid page returned: %s" % page_title)

        return page

    def get_page_info(self, page_id):
        """
        Get page information including ancestors, version.
        :param string page_id: id of the confluence page
        :return json conf_resp: response from the confluence
        """
        conf_rest_url = (
            self.confluence_url
            + "/rest/api/content/"
            + page_id
            + "?expand=ancestors,version"
        )
        resp = _session.get(conf_rest_url, **self.req_kwargs)
        resp.raise_for_status()
        return resp.json()

    def create_page(self, space, page_title, ancestor=None):
        """
        Creates a page with title in space.
        :param string space : space to be used in confluence
        :param string page_title : Title of page to be created in confluence
        :return json conf_resp: response from the confluence
        """
        data = {
            "type": "page",
            "title": page_title,
            "space": {"key": space.strip('"')},
            "body": {
                "storage": {
                    "value": "<p>Empty page</p>", "representation": "storage"
                }
            },
        }

        if ancestor:
            data['ancestors'] = [{"id": ancestor}]

        resp = _session.post(
                self.confluence_rest_url, json=data, **self.req_kwargs)
        if not resp.ok:
            logger.debug("Confluence response: %s", resp.text)
        resp.raise_for_status()

        return resp.json

    @retry(wait_on=requests.exceptions.HTTPError)
    def update_page(self, page_id, markup):
        """
        Updates the page with id page_id.
        :param string page_id: id  of the page
        :param string markup : markup content of the page
        :return json conf_resp: response from the confluence
        """
        url = self.confluence_rest_url + page_id
        info = self.get_page_info(page_id)
        updated_page_version = int(info["version"]["number"] + 1)
        digest = hashlib.sha256(markup.encode('utf-8')).hexdigest()

        data = {
            'id': str(page_id),
            'type': 'page',
            'title': info['title'],
            'version': {
                'number': updated_page_version,
                'minorEdit': True,
                'message': digest,
            },
            'body': {'storage': {'representation': 'wiki', 'value': markup}},
        }
        resp = _session.put(url, json=data, **self.req_kwargs)
        if not resp.ok:
            logger.debug("Confluence response: %s", resp.json())
        resp.raise_for_status()

        return resp.json()

    def get_auth_object(self):
        """
        Returns Auth object based on auth type.
        :return : Auth Object
        """
        if self.authtype == "basic":
            return HTTPBasicAuth(self.username, self.password)
        if self.authtype == "token":
            return BearerAuth(self.token)
