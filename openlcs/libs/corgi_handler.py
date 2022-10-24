import asyncio
import httpx
import os
import re
import requests
import sys
import uuid
import uvloop
from concurrent.futures import ThreadPoolExecutor
from urllib import parse

openlcs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if openlcs_dir not in sys.path:
    sys.path.append(openlcs_dir)
from libs.common import group_components  # noqa: E402

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


class ContainerComponentsAsync:
    """
    Get container component data list from Corgi
    """
    def __init__(self, base_url, container_nvr):
        self.base_url = base_url
        self.container_nvr = container_nvr
        self.endpoint = f"{self.base_url}components"

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

    def get_component_and_links(self, nvr, component_type="CONTAINER_IMAGE"):
        """
        Get component links in one of "CONTAINER_IMAGE" type container
        component with container nvr.
        """
        component_links = []
        container_component = {}
        if nvr:
            params = {'type': component_type, 'nvr': nvr}
            response = requests.get(
                self.endpoint, params=params)
            if response.status_code == 200:
                try:
                    results = response.json().get('results')
                    for result in results:
                        # Currently, we only need arch='src' components.
                        if result.get('arch') != 'src':
                            continue
                        else:
                            container_component = self.get_component_flat(
                                result)
                            provides = result.get('provides')
                            for provide in provides:
                                component_links.append(provide.get('link'))
                            break
                except Exception as e:
                    raise RuntimeError(e) from None
        else:
            err_msg = "Should provide a container nvr."
            raise ValueError(err_msg)
        return component_links, container_component

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
        with httpx.Client(timeout=None) as client:
            cert = os.getenv("REQUESTS_CA_BUNDLE")
            response = client.get(
                component_link,
                params={'cert': cert})
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

    async def get_event_loop(self, executor, component_links):
        """
        Event loop function for component links.
        """
        loop = asyncio.get_event_loop()
        futures = [
            loop.run_in_executor(
                executor, self.get_component_data, component_link)
            for component_link in component_links
        ]
        return await asyncio.gather(*futures)

    def get_components_data(self):
        # Create a limited thread pool
        executor = ThreadPoolExecutor(max_workers=5,)
        event_loop = asyncio.get_event_loop()
        components = []
        component_links, container_component = self.get_component_and_links(
            self.container_nvr)
        if component_links and container_component:
            try:
                components = event_loop.run_until_complete(
                    self.get_event_loop(executor, component_links)
                )
            except Exception as e:
                raise RuntimeError(e) from None
            finally:
                event_loop.close()
        if container_component:
            components.append(container_component)
        return group_components(components) if components else {}


class ProductVersion:
    """
    Handle container product name and release
    """
    def __init__(self, base_url, product_release):
        self.base_url = base_url
        self.product_release = product_release

    def get_product_version(self, fields=None) -> dict:
        endpoint = f"{self.base_url}product_versions"
        params = {'name': self.product_release}
        if fields is None:
            fields = ['name', 'ofuri', 'description', 'products', 'components']
        data = requests.get(endpoint, params=params).json()
        # 0 or 1 result for product version name query
        retval = dict()
        if data['count'] > 0:
            product_data = data['results'][0]
            for field in fields:
                retval[field] = product_data[field]
        return retval
