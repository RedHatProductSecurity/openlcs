import asyncio
import httpx
import logging
import os
import re
import requests
from requests.exceptions import RequestException, HTTPError
import sys
import uuid
import uvloop
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from urllib import parse


openlcs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if openlcs_dir not in sys.path:
    sys.path.append(openlcs_dir)
from libs.common import group_components  # noqa: E402
from libs.common import find_srpm_source

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


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

    def get(self, url, query_params=None,
            excludes=self.default_exclude_fields, timeout=30):
        if not query_params:
            query_params = {}
        # exclude costly related field queries by default.
        query_params['exclude_fields'] = ','.join(excludes)
        response = self.session.get(url, params=query_params)
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
            'synced': True
        }

    def get_component_and_links(self, nvr, component_type):
        """
        Get links in Corgi for components in "OCI" or "RPMMOD".
        """
        route = "components"
        component_links = []
        parent_component = {}
        if nvr:
            params = {'type': component_type, 'nvr': nvr}
            response = self.session.get(
                f"{self.base_url}{route}", params=params, timeout=10)
            if response.status_code == 200:
                try:
                    results = response.json().get('results')
                    for result in results:
                        # This part is only for contianer, won't share this
                        # condition with Module
                        # Currently, we only need arch='src' components.

                        if result.get('arch') != 'src' and\
                                component_type == "OCI":
                            continue
                        else:
                            parent_component = self.get_component_flat(result)
                            provides = result.get('provides')
                            for provide in provides:
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
                'synced': False
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
                'synced': False
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
        with httpx.Client(timeout=None, verify=context) as client:
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
        if parent_component:
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
            try:
                data = self.get(url, query_params=query_params)
                yield from data["results"]
                url = data.get("next")
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
        Returns the source rpm component for `component`
        """
        if component["arch"] == "src":
            return component
        else:
            sources = component.get("sources")
            if not sources:
                return None
            link = find_srpm_source(sources)
            if link:
                logger.info(f"Querying component: {link}")
                return self.get(link)
            return None

    def fetch_component(self, link):
        component = self.get(link)
        if component.get("type") == "RPM":
            return self.get_srpm_component(component)
        return component

    def get_container_source_components(self, component):
        """
        Extract source components from a corgi container component

        If the name of the component ends with "-source", it will be handled
        separately. Otherwise the function looks for binary components
        provided by the component and retrieves their corresponding
        source components. The source components are returned as a list.

        Args:
        component (dict): The OCI component info

        Returns:
        list: A list of source components found.
        """
        name = component.get("name")
        if name.endswith("-source"):
            logger.debug("This is a source container build")
            sources = component.get("sources")
            if not sources:
                return None
            link = sources[0].get("link")
            component = self.get(link)
            logger.debug(f"Binary build {component['nevra']} retrieved.")

        provides = component.get("provides", [])
        links = [provide.get("link") for provide in provides]
        logger.debug(f"List of provides({len(links)}) collected")

        components_extracted = list()
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=3
        ) as executor:
            tasks = {
                executor.submit(
                    self.fetch_component, link): link for link in links}
            for task in concurrent.futures.as_completed(tasks):
                result = task.result()
                components_extracted.append(result)
                logger.debug(f"Provides {result['nevra']} retrieved.")
        # Remove duplicates
        component_set = set(tuple(c.items()) for c in components_extracted)
        return [dict(c) for c in component_set]

    def get_source_component(self, component):
        component_type = component.get("type")
        if component_type == "RPM":
            return self.get_srpm_component(component)
        elif component_type == "OCI":
            return self.get_container_source_components(component)
        else:
            # FIXME: add golang/npm/cargo/pip/maven here.
            raise ValueError("Unsupported type")

def main():
    connector = CorgiConnector()
    url = ("https://corgi-stage.prodsec.redhat.com/api/v1/components/"
           "000be063-14ef-4fcc-8e56-397cfc4a0b10")
    component = connector.get(url)
    logger.debug(f"Component {component['nevra']} retrieved.")
    provides = connector.get_container_source_components(component)
    return provides

if __name__ == "__main__":
    provides = main()
    print("\n".join([c.get("purl") for c in provides]))
