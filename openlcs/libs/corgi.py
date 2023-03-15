import asyncio
import httpx
import logging
import os
import re
import requests
from requests.exceptions import RequestException, HTTPError
import sys
import time
import uuid
import uvloop
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from urllib import parse

openlcs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if openlcs_dir not in sys.path:
    sys.path.append(openlcs_dir)
from libs.common import group_components  # noqa: E402
from libs.common import find_srpm_source  # noqa: E402
from libs.common import remove_duplicates_from_list_by_key  # noqa: E402
from libs.exceptions import MissingBinaryBuildException  # noqa: E402

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


logger = logging.getLogger(__name__)
# Turn on debug mode if you want more verbose logs
logging.basicConfig(level=logging.INFO)


def corgi_include_exclude_fields_wrapper(func):
    def wrapper(*args, **kwargs):
        query_params = kwargs.get('query_params', {})
        # work around for latencies by excluding costly related fields
        # queries, see also CORGI-482, another benefit is to minimize
        # the data returned, see OLCS-471
        includes = kwargs.pop('includes', None)
        excludes = kwargs.pop('excludes', None)
        # For apis other than the `/components` endpoint, includes/excludes
        # don't do any harm fortunately.
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
            base_url = os.getenv("CORGI_API_PROD")
        self.base_url = base_url
        # corgi stage support this at the moment.
        self.default_exclude_fields = (
            "products",
            "product_versions",
            "product_streams",
            "product_variants",
            "channels",
        )
        self.session = requests.Session()

    @staticmethod
    def get_include_fields(component_type: str):
        """
        Returns bare-minimum include fields needed based on component_type.

        Only used for corgi's /components endpoint.
        """
        fields = []
        # basic fields needed, all calls should include these fields
        base_fields = [
            "uuid", "name", "version", "release", "arch", "type",
            "purl", "link", "nvr", "nevra", "download_url",
            "license_declared", "software_build"
        ]
        fields.extend(base_fields)

        if component_type.upper() == "RPM":
            fields.remove("download_url")
            # sources could be a long list, need to truncate after obtained
            fields.append("sources")
        elif component_type.upper() in ["OCI", "RPMMOD"]:
            fields.remove("download_url")
            fields.append("provides")
        else:
            # FIXME: any specific fields needed for other types?
            # software_build does not make much sense for non-rpm/non-ocis.
            fields.remove("software_build")

        return fields

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

    def get_sync_fields(self, component_uuid):
        """
        Determines which fields to sync for a specified component.
        """
        sync_fields = [
            "openlcs_scan_url",
            "openlcs_scan_version",
            "license_declared",
            "license_concluded",
            "copyright_text",
        ]
        # FIXME: if the original component data is preserved, we don't need
        # to `get` it again.
        url = f"{self.base_url}components/{component_uuid}"
        component = self.get(url)
        # Update of non-empty `license_declared` in corgi is forbidden.
        # overwrite of other fields are possible. See also CORGI-475
        if component.get("license_declared"):
            sync_fields.remove("license_declared")

        return sync_fields

    def sync_to_corgi(self, component_data):
        """
        sync specified fields to corgi(via PUT)
        """
        component_uuid = component_data.get("uuid")
        fields = self.get_sync_fields(component_uuid)
        # FIXME: use constraint SPDX identifiers for declared licenses
        # see also CORGI-440
        data = {k: v for k, v in component_data.items() if k in fields and v}
        url = f"{self.base_url}components/{component_uuid}/olcs_test"
        response = self.session.put(url, data=data)
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
            return (True, component)
        sources = component.get("sources")
        if not sources:
            # This is not likely to happen since corgi promises
            # to always have corresponding srpm.
            return (False, component.get("purl"))
        link = find_srpm_source(sources)
        if link:
            logger.info("Querying component: %s", link)
            component = self.get(link)
            return (True, component) if component else (False, link)
        else:
            return (False, component.get("purl"))

    def _fetch_component(self, link):
        """
        shortcut to retrieve container "provides" component
        """
        component = self.get(link, excludes=self.default_exclude_fields)
        if component:
            if component.get("type") == "RPM":
                return self.get_srpm_component(component)
            # FIXME: examine what to return for non-rpm components.
            return (True, component)
        else:
            return (False, link)

    def get_container_source_components(self, component, subscribed_purls=None,
                                        max_workers=5):
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
        Tuple: (components found / missings)
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
            component = self.get(link)
            logger.debug("Binary build %s retrieved.", component['nevra'])

        oci_provides = component.get("provides", [])
        links = []
        for provide in oci_provides:
            purl = provide.get("purl")
            # exclude those that are already retrieved earlier
            if subscribed_purls and purl in subscribed_purls:
                continue
            links.append(provide.get("link"))
        logger.debug("List of provides(%d) collected", len(links))

        components_extracted = list()
        components_missing = set()
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers
        ) as executor:
            tasks = {
                executor.submit(
                    self._fetch_component, link): link for link in links}
            for task in concurrent.futures.as_completed(tasks):
                success, result = task.result()
                if success:
                    components_extracted.append(result)
                    logger.debug("Provides %s retrieved.", result['nevra'])
                else:
                    components_missing.add(result)
                    logger.error("Provides %s missing.", result)
        # Remove duplicates
        components = remove_duplicates_from_list_by_key(
            components_extracted, "uuid")
        return (components, list(components_missing))

    def get_source_component(self, component, subscribed_purls=None):
        component_type = component.get("type")
        if component_type == "RPM":
            return self.get_srpm_component(component)
        elif component_type in ["OCI", "RPMMOD"]:
            return self.get_container_source_components(
                component, subscribed_purls)
        else:
            return (True, component)

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
