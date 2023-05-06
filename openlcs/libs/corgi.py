import asyncio
import concurrent.futures
import functools
import httpx
import logging
import os
import re
import requests
import sys
import time
import uuid
import uvloop

from concurrent.futures import ThreadPoolExecutor
from packageurl import PackageURL
from requests.exceptions import RequestException, HTTPError
from requests.status_codes import codes as http_codes
from urllib import parse
from urllib.parse import urljoin

from django.core.cache import cache

openlcs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if openlcs_dir not in sys.path:
    sys.path.append(openlcs_dir)
from libs.common import get_nvr_from_purl  # noqa: E402
from libs.common import get_oidc_auth_url  # noqa: E402
from libs.common import group_components  # noqa: E402
from libs.common import find_srpm_source  # noqa: E402
from libs.common import remove_duplicates_from_list_by_key  # noqa: E402
from libs.common import is_prod  # noqa: E402
from libs.exceptions import MissingBinaryBuildException  # noqa: E402

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


logger = logging.getLogger(__name__)
# Turn on debug mode if you want more verbose logs
logging.basicConfig(level=logging.INFO)

CORGI_SYNC_FIELDS = [
    "openlcs_scan_url",
    "openlcs_scan_version",
    "license_declared",
    "license_concluded",
    "copyright_text",
]

OIDC_CLIENT_SECRET = os.getenv("OPENLCS_OIDC_CLIENT_SECRET", "")
OIDC_CLIENT_NAME = "openlcs"
# B105: hardcoded_password_string -> not a hardcoded password but a name
# of the key under which the access token is stored in the cache.
OIDC_ACCESS_TOKEN_CACHE_KEY = "oidc_access_token"  # nosec: B105


def corgi_include_exclude_fields_wrapper(func):
    def wrapper(*args, **kwargs):
        # Only apply on components endpoint
        _, url = args
        if "/components" in url:
            query_params = kwargs.get('query_params', {})
            # work around for latencies by excluding costly related fields
            # queries, see also CORGI-482, another benefit is to minimize
            # the data returned, see OLCS-471
            includes = kwargs.pop('includes', None)
            excludes = kwargs.pop('excludes', None)
            if excludes:
                query_params['exclude_fields'] = ','.join(excludes)
            if includes:
                query_params['include_fields'] = ','.join(includes)
                # includes/excludes are mutually exclusive, the former
                # takes precedence.
                query_params.pop('exclude_fields', None)
            kwargs['query_params'] = query_params
        return func(*args, **kwargs)

    return wrapper


class CorgiConnector:
    """
    Get parent component data list from Corgi
    """
    def __init__(self, base_url=None):
        if base_url is None:
            # corgi api endpoint available in environment variable
            base_url = self.get_api_endpoint()
        self.base_url = base_url
        self.session = requests.Session()

    def get_api_endpoint(self):
        if is_prod():
            return os.getenv("CORGI_API_PROD")
        return os.getenv("CORGI_API_STAGE")

    def get_oidc_access_token(self):
        """
        Get the OIDC access token, it can be used for authentication.
        """
        access_token = cache.get(OIDC_ACCESS_TOKEN_CACHE_KEY)
        if not access_token:
            response = self.session.post(
                get_oidc_auth_url(),
                auth=(OIDC_CLIENT_NAME, OIDC_CLIENT_SECRET),
                data={"grant_type": "client_credentials"},
            )
            response.raise_for_status()
            response_data = response.json()

            # E.g. "Bearer 1234abcd"
            access_token = f"{response_data['token_type']} {response_data['access_token']}"  # noqa
            cache.add(
                key=OIDC_ACCESS_TOKEN_CACHE_KEY,
                value=access_token,
                # Expire token earlier to account for network latency
                timeout=response_data["expires_in"] - 5,  # seconds
            )
        return access_token

    @staticmethod
    def get_corgi_access_token():
        """
        Get the access token for the Corgi user(openlcs).
        """
        return f"Token {os.getenv('CORGI_ACCESS_TOKEN')}"

    def corgi_request(self, path, access_token, method, **kwargs):
        """
        Use this function to start a corgi reqeust.
        """
        url = urljoin(self.base_url, path)
        response = self.session.request(
            method=method,
            url=url,
            headers={"Authorization": access_token},
            **kwargs,
        )
        if response.status_code == http_codes.FORBIDDEN:
            err_msg = f"Failed to authenticate with Corgi: {response.text}"
            raise RuntimeError(err_msg)
        return response

    @staticmethod
    def get_include_fields(component_type=""):
        """
        Returns bare-minimum include fields needed based on component_type.

        Only used for corgi's /components endpoint.
        """
        fields = []
        # basic fields needed, all calls should include these fields
        # any type-indenpendent fields should go here.
        base_fields = [
            "uuid", "name", "version", "release", "arch", "type",
            "purl", "link", "nvr", "nevra", "download_url", "related_url",
            "license_declared", "software_build", "openlcs_scan_url"
        ]
        fields.extend(base_fields)

        if component_type.upper() == "RPM":
            # sources could be a long list, need to truncate after obtained
            fields.append("sources")
            fields.remove("download_url")
        elif component_type.upper() in ["OCI", "RPMMOD"]:
            fields.append("provides")
            fields.remove("download_url")
            # No openlcs_scan_url will be provided for oci or rhelmod
            fields.remove("openlcs_scan_url")
        else:
            # FIXME: any specific fields needed for other types?
            # software_build makes no sense for non-rpm/non-ocis components.
            fields.remove("software_build")

        return fields

    # Inspired from https://gitlab.com/mh21/ocp-sso-token/-/blob/
    # main/ocp_sso_token/ocp_oauth_login.py#L21
    @functools.cached_property
    def rpm_includes(self):
        return self.get_include_fields(component_type="rpm")

    @functools.cached_property
    def oci_includes(self):
        return self.get_include_fields(component_type="oci")

    @functools.cached_property
    def rpmmod_includes(self):
        return self.get_include_fields(component_type="rpmmod")

    @functools.cached_property
    def default_includes(self):
        return self.get_include_fields()

    @staticmethod
    def truncate_rpm_component_sources(component):
        """
        "sources" can be an extreamly long list, this function truncate the
        redundant ones, leaving the idential source rpm.
        """
        # srpm component has no sources
        if component["arch"] == "src":
            return component
        sources = iter(component["sources"])
        source = find_srpm_source(sources)
        # Truncate unneeded sources.
        component["sources"] = [source] if source is not None else []
        return component

    @corgi_include_exclude_fields_wrapper
    def get(self, url, query_params=None, timeout=30, max_retries=5,
            retry_delay=10, includes=None, excludes=None):
        for i in range(max_retries + 1):
            try:
                response = self.session.get(
                    url, params=query_params, timeout=timeout)
                response.raise_for_status()
                return response.json()
            except (RequestException, HTTPError) as e:
                if i == max_retries:
                    logger.error(
                        "Request exception after %d retries: %s", i, e)
                    return None
                else:
                    logger.warning(
                        "Request exception: %s. Retry after %d seconds...",
                        e, retry_delay)
                    time.sleep(retry_delay)

    @classmethod
    def get_sync_fields(cls, component):
        """
        Determines which fields to sync for a specified component.
        """
        sync_fields = CORGI_SYNC_FIELDS.copy()
        # Don't overwrite `license_declared` if corgi already has.
        if component.get("license_declared"):
            sync_fields.remove("license_declared")

        return sync_fields

    def sync_to_corgi(self, component_data, fields):
        """
        sync specified fields to corgi(via PUT)
        """
        component_uuid = component_data.get("uuid")
        # FIXME: use constraint SPDX identifiers for declared licenses
        #  see also CORGI-440
        data = {k: v for k, v in component_data.items() if k in fields and v}
        # Corgi changed the sync API:
        # https://github.com/RedHatProductSecurity/component-registry/pull/424
        path = f"components/{component_uuid}/update_license"
        # TODO: Currently we use Corgi token as a template solution, we will
        #  change back to OIDC SSO token in the feature.
        access_token = self.get_oidc_access_token()
        response = self.corgi_request(path, access_token, "PUT", data=data)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def get_component_flat(data):
        return {
            "uuid": data.get("uuid"),
            "type": data.get("type"),
            "name": data.get("name"),
            "version": data.get("version"),
            "release": data.get("release", ""),
            "summary_license": data.get("license", ""),
            "arch": data.get("arch", ""),
        }

    def get_component_and_links(self, nvr, component_type):
        """
        Get links in Corgi for components in "OCI" or "RPMMOD".
        """
        route = "components"
        component_links = []
        parent_component = {}
        if nvr:
            params = {'type': component_type, 'nvr': nvr, 'arch': 'x86_64'}
            response = self.session.get(
                f"{self.base_url}{route}", params=params, timeout=10)
            if response.status_code == 200:
                try:
                    results = response.json().get('results')
                    for result in results:
                        parent_component = self.get_component_flat(result)
                        provide_components = result.get('provides')
                        for provide in provide_components:
                            component_links.append(provide.get('link'))
                        break
                except Exception as e:
                    raise RuntimeError(e) from None
        else:
            err_msg = "Should provide a container or module nvr."
            raise ValueError(err_msg)
        return component_links, parent_component

    def unquote_link(self, link):
        """
        Unquote link that quote many times.
        """
        link = parse.unquote(link)
        if "%" in link:
            link = self.unquote_link(link)
        return link

    def parse_component_link(self, component_link):
        """
        Get the component data according to parse the component link.
        """
        component = {}
        unquote_component_link = self.unquote_link(component_link)
        rpm_pattern = re.compile(
            r'.*=pkg:(?P<type>.*)/redhat/(?P<name>.*)@(?P<version>.*)-(?P<release>.*)\?arch=(?P<arch>.*)')  # noqa
        remote_source_pattern = re.compile(
            r'.*=pkg:(?P<type>.*?)/(?P<name>.*)@(?P<version>.*)')
        match = rpm_pattern.match(unquote_component_link)
        if match:
            component = {
                'uuid': str(uuid.uuid4()),
                'type': match.group('type').upper(),
                'name': match.group('name'),
                'version': match.group('version'),
                'release': match.group('release'),
                'arch': match.group('arch'),
                'summary_license': '',
            }

        if not match:
            # For remote source, the 'release' and 'arch' data are ''.
            match = remote_source_pattern.match(unquote_component_link)
            component = {
                'uuid': str(uuid.uuid4()),
                'type': match.group('type').upper(),
                'name': match.group('name'),
                'version': match.group('version'),
                'release': '',
                'arch': '',
                'summary_license': '',
            }
        if component:
            return component
        else:
            err_msg = "Failed to parse component data from component link"
            raise RuntimeError(err_msg)

    def get_component_data_from_corgi(self, component_link):
        """
        Get component data from the response of corgi component link.
        """
        component = {}
        # Explicitly pass in the ssl context for httpx client. See also
        # https://www.python-httpx.org/advanced/#ssl-certificates
        cert = os.getenv("REQUESTS_CA_BUNDLE")
        context = httpx.create_ssl_context(verify=cert)
        with httpx.Client(timeout=60, verify=context) as client:
            response = client.get(component_link)
            if response.status_code == 200:
                content = response.json()
                component = self.get_component_flat(content)
        return component

    def get_component_data(self, component_link):
        """
        Get component data from the response of component link.
        """
        component = self.get_component_data_from_corgi(component_link)
        if not component:
            # Then try to parse the component data via its link
            component = self.parse_component_link(component_link)
        return component

    async def get_event_loop(self, executor, component_links, loop):
        """
        Event loop function for component links.
        """
        futures = [
            loop.run_in_executor(
                executor, self.get_component_data, component_link)
            for component_link in component_links
        ]
        return await asyncio.gather(*futures)

    def get_components_data(self, nvr, component_type):
        # Create a limited thread pool
        executor = ThreadPoolExecutor(max_workers=5,)
        asyncio.set_event_loop(asyncio.new_event_loop())
        event_loop = asyncio.get_event_loop()
        components = []
        component_links, parent_component = self.get_component_and_links(
            nvr, component_type)
        if component_links and parent_component:
            try:
                components = event_loop.run_until_complete(
                    self.get_event_loop(executor, component_links, event_loop)
                )
            except Exception as e:
                raise RuntimeError(e) from None
            finally:
                event_loop.close()
        if components and parent_component:
            components.append(parent_component)
        return group_components(components) if components else {}

    def get_product_version(self, name, fields=None) -> dict:
        # API route for corgi product_versions endpoint
        route = "product_versions"
        params = {"name": name}
        if fields is None:
            fields = ["name", "ofuri", "description", "products", "components"]
        data = self.session.get(f"{self.base_url}{route}", params=params,
                                timeout=10).json()
        # 0 or 1 result for product version name query
        retval = dict()
        if data["count"] > 0:
            product_data = data["results"][0]
            for field in fields:
                retval[field] = product_data[field]
        return retval

    def deduplicate_provides(self, oci_noarch_provides):
        # Deduplicate provides for components with different arch.
        nvrs = []
        provides = []
        for oci_noarch_provide in oci_noarch_provides:
            purl = oci_noarch_provide.get('purl')
            if purl.startswith('pkg:rpm'):
                nvr = get_nvr_from_purl(purl)
                if nvr not in nvrs:
                    nvrs.append(nvr)
                    provides.append(oci_noarch_provide)
            else:
                provides.append(oci_noarch_provide)
        return provides

    def get_paginated_data(self, query_params=None, api_path="components"):
        """
        Retrieves paginated data from `api_path`.

        The implementation assumes that the API endpoint returns paginated
        data with following form:
        {
            "previous": url of the previous page (if any),
            "next": url of the next page (if any),
            "results": a list of data
        }

        :param query_params: a dictionary of query parameters.
        :param api_path: the path of the API endpoint, default to "components"
        :return: yields each page of data as a list
        """
        url = f"{self.base_url}{api_path}"
        while url:
            data = self.get(url, query_params=query_params)
            try:
                if isinstance(data, dict) and "results" in data:
                    # Paginated response with "results" key
                    yield from data["results"]
                    url = data.get("next")
                    # query_params is needed once and only once
                    if query_params:
                        query_params = None
                else:
                    # Hack to survive an edge case(query by purl or possibly
                    # other unidentified fields) that when only one instance
                    # is retrieved, the api endpoint returns the model repr
                    # instead of following the drf pagination convention.
                    yield data
                    break
            except HTTPError as e:
                # non-200 responses
                logger.error("HTTP Error: %s", e)
                break
            except RequestException as e:
                # general exceptions, timeout/connection/maxredirect etc.
                logger.error("Request failed: %s", e)
                break

    def get_srpm_component(self, component):
        """
        Returns the source rpm component for an RPM component
        """
        if component["type"] != "RPM":
            raise ValueError(f"Unsupported component type {component['type']}")
        if component["arch"] == "src":
            return component
        sources = component.get("sources")
        if not sources:
            # This is not likely to happen since corgi promises
            # to always have corresponding srpm.
            return component.get("purl")
        link = sources[0].get("link")
        if link:
            logger.info("Querying component: %s", link)
            component = self.get(link, includes=self.rpm_includes)
            if component:
                return component
            return link
        else:
            return component.get("purl")

    def _fetch_component(self, link, component_type):
        """
        shortcut to retrieve container "provides" component
        """
        # rpm/oci/rpmmod are cached properties
        includes = getattr(self, f"{component_type.lower()}_includes",
                           self.default_includes)
        component = self.get(link, includes=includes)
        if component:
            if component.get("type") == "RPM":
                component = CorgiConnector.truncate_rpm_component_sources(
                    component)
                return self.get_srpm_component(component)
            # FIXME: examine what to return for non-rpm components.

            # Filter go-package component for GOLANG type
            if component.get("type") == "GOLANG":
                return self.filter_go_package_component(component)

            return component
        else:
            return link

    def get_container_source_components(self, component, subscribed_purls=None,
                                        max_workers=4, max_queue_length=6):
        """
        Extract source components from a corgi container component

        If the name of the component ends with "-source", it will be handled
        separately. Otherwise, the function looks for binary components
        provided by the component and retrieves their corresponding
        source components. The source components are returned as a list.
        There are chances that after several retries the component retrieval
        still fails, failed ones are returned as a list of strings.

        Args:
        component (dict): The OCI component info

        Returns:
        Generator: the execution result from `future.result()`, consisting
        of data(dict) for successful query or data(purl string) for failures.
        See also `source_component_to_list` on how it's consumed.
        """
        name = component.get("name")
        if name.endswith("-source"):
            logger.debug("This is a source container build")
            sources = component.get("sources")
            # There are cases when a "-source" components in corgi does not
            # have a corresponding binary build, see also OLCS-459.
            if not sources:
                message = (f"Failed to find binary build for "
                           f"{component['nevra']} in component registry")
                logger.debug(message)
                raise MissingBinaryBuildException(message)

            link = sources[0].get("link")
            component = self.get(link, includes=self.oci_includes)
            logger.debug("Binary build %s retrieved.", component['nevra'])
        if component.get('arch') == 'noarch':
            oci_noarch_provides = component.get("provides", [])
        else:
            # If the binary container arch is not noarch, get the provides
            # of the provides of the noarch container.
            if component.get('sources'):
                link = component.get('sources')[0].get("link")
                noarch_oci = self.get(link, includes=self.oci_includes)
                oci_noarch_provides = noarch_oci.get("provides", [])
        # For the noarch binary container, the different arch provides match
        # only one src component. Deduplication of these kind of provides
        # helps the performance.
        oci_provides = self.deduplicate_provides(oci_noarch_provides)
        # Store deduplicated provides
        provides = []
        for provide in oci_provides:
            purl = provide.get("purl")
            # exclude those that are already retrieved earlier
            if subscribed_purls and purl in subscribed_purls:
                continue
            purl_dict = PackageURL.from_string(purl).to_dict()
            component_type = purl_dict.get("type", "")
            # OCI component of a different arch may present in "provides".
            # Get rid of it.
            if component_type.upper() == "OCI":
                continue
            provides.append((provide.get("link"), component_type))
        logger.debug("List of provides(%d) collected", len(provides))
        remaining_provides = len(provides)
        provides_iter = iter(provides)

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers
        ) as executor:
            tasks = {}
            while remaining_provides > 0:
                for provide in provides_iter:
                    link, component_type = provide
                    task = executor.submit(self._fetch_component,
                                           link, component_type)
                    tasks[task] = link
                    # number of tasks to be in the queue. Larger number means
                    # slightly higher memory consumption.
                    if len(tasks) > max_queue_length:
                        break
                for task in concurrent.futures.as_completed(tasks):
                    remaining_provides -= 1
                    result = task.result()
                    yield result
                    del tasks[task]

    def filter_go_package_component(self, component):
        """
        Pass a GOLANG type component
        Filter go-package component, if component is a
        go-package component, return None
        """
        url = f"{self.base_url}components"
        result = self.get(
            url,
            query_params={
                "nevra": component['nevra'],
                "gomod_components": True
            }
        )

        return None if result["count"] == 0 else component

    def get_source_component(self, component, subscribed_purls=None):
        component_type = component.get("type")
        if component_type == "RPM":
            component = CorgiConnector.truncate_rpm_component_sources(
                component)
            yield self.get_srpm_component(component)
        elif component_type in ["OCI", "RPMMOD"]:
            yield from self.get_container_source_components(
                component, subscribed_purls)
        # for GOLANG type component, filter go-package type
        elif component_type == "GOLANG":
            yield self.filter_go_package_component(component)
        else:
            yield component

    @classmethod
    def source_component_to_list(cls, gen):
        """
        Called after `CorgiConnector.get_source_component`, to change the
        generator returned to a tuple of list.
        """
        components = []
        missings = []
        for data in gen:
            if isinstance(data, dict):
                components.append(data)
            # None means no need to process
            elif data is None:
                continue
            else:
                missings.append(data)
        components = remove_duplicates_from_list_by_key(components, "uuid")
        return (components, missings)

    def get_component_instance_from_nvr(self, nvr):
        params = {'nvr': nvr}
        response = self.session.get(
            f"{self.base_url}components", params=params, timeout=10)
        if response.status_code == 200:
            if results := response.json().get('results'):
                if len(results) == 1:
                    return results[0].get('link')
                else:
                    for result in results:
                        if result.get('arch') == 'x86_64':
                            return result.get('link')

        err_msg = f"Failed to find {nvr} component instance from Corgi."
        raise ValueError(err_msg)

    def collect_components_from_subscriptions(self,
                                              subscriptions,
                                              num_components=100):
        """
        Collect source components based on subscriptions.

        Due to the fact the each subscription may have extreamly long number
        of components which end up with high memory consumption if we return
        data at once, this function provides a mechanism to dynamically yield
        components, based on the `should_yield_data` inner function.
        """
        def process_component(component, subscribed_purls=None):
            sources = []
            missings = []
            gen = self.get_source_component(
                component, subscribed_purls)
            components, missings = CorgiConnector.source_component_to_list(gen)
            if component.get("type") in ["OCI", "RPMMOD"]:
                # Nest source components in `olcs_sources`
                component["olcs_sources"] = components
                sources.append(component)
            else:
                sources.extend(components)
                missings.extend(missings)
            return (sources, missings)

        def should_yield_data(component, result):
            """
            Helper function, to decide whether to yield result under
            specified condition.
            """
            return (
                component["type"] == "OCI"
                or len(result["sources"]) >= num_components
            )

        for subscription in subscriptions:
            query_params = subscription.get("query_params")
            if not query_params:
                continue
            # subscription purls obtained from previous sync
            subscribed_purls = subscription.get("component_purls", [])

            components = self.get_paginated_data(query_params)
            result = {"subscription_id": subscription["id"]}
            while True:
                try:
                    component = next(components)
                except StopIteration:
                    # StopIteration may appear when `should_yield_data` is
                    # False, i.e., the last iteration(before exhausting) may
                    # accumulates components less than `num_components`.
                    if len(result) > 1:
                        yield result
                    break
                else:
                    subscription_sources, subscription_missings = [], []
                    if component["purl"] in subscribed_purls:
                        # excludes components processed in previous sync.
                        continue
                    try:
                        sources, missings = process_component(
                            component, subscribed_purls)
                    except MissingBinaryBuildException as e:
                        logger.error(str(e))
                        # FIMXE: subsequent calls for missing binary build
                        # component will likely to fail again.
                        subscription_missings.append(component["purl"])
                        continue
                    else:
                        subscription_sources.extend(sources)
                        subscription_missings.extend(missings)
                        result.setdefault("sources", []).extend(
                            subscription_sources)
                        result.setdefault("missings", []).extend(
                            subscription_missings)
                        if should_yield_data(component, result):
                            yield result
                            # reset result to the original state
                            del result["sources"]
                            del result["missings"]
