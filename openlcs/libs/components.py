import asyncio
import httpx
import ijson
import re
from urllib import parse
from urllib.request import urlopen


class ContainerComponents:
    """
    Get container component data list from Corgi
    """

    def __init__(self, base_url):
        self.base_url = base_url

    def get_component_links(self, nvr, component_type="CONTAINER_IMAGE"):
        """
        Get component links in one of "CONTAINER_IMAGE" type container
        component with container nvr.
        """
        component_links = []
        if nvr:
            try:
                search_url = f"{self.base_url}?type={component_type}&nvr={nvr}"
                data = urlopen(search_url)
                results = ijson.items(data, 'results.item')
                # Only use provides in one of container components.
                provides = results.__next__().get('provides')
                for provide in provides:
                    component_links.append(provide.get('link'))
                del results
            except Exception as e:
                err_msg = f'Failed to get component links. Reason: {e}'
                raise RuntimeError(err_msg) from None
        else:
            err_msg = "Should provide the container nvr."
            raise ValueError(err_msg)
        return component_links

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
            r'.*=pkg:(?P<type>.*)/redhat/(?P<name>.*)@(?P<version>.*)-(?P<release>.*)\?arch=.*')  # noqa
        remote_source_pattern = re.compile(
            r'.*=pkg:(?P<type>.*?)/(?P<name>.*)@(?P<version>.*)')
        match = rpm_pattern.match(unquote_component_link)
        if match:
            component = {
                'name': match.group('name'),
                'version': match.group('version'),
                'release': match.group('release'),
                'type': match.group('type').upper()
            }
            component['nvr'] = "{name}-{version}-{release}".format(**component)

        if not match:
            match = remote_source_pattern.match(unquote_component_link)
            component = {
                'name': match.group('name'),
                'version': match.group('version'),
                'type': match.group('type').upper()
            }
            component['nvr'] = "{name}-{version}".format(**component)

        if component:
            return component
        else:
            err_msg = "Failed to parse component data from component link"
            raise RuntimeError(err_msg)

    @staticmethod
    async def get_component_data_from_corgi(component_link):
        """
        Get component data from the response of corgi component link.
        """
        component = {}
        async with httpx.AsyncClient(verify=False, timeout=None) as client:
            response = await client.get(component_link)
            if response.status_code == 200:
                content = response.json()
                component_type = content.get('type')
                # For RPMs.
                if component_type == "RPM":
                    component = {
                        'nvr': content.get('nvr'),
                        'name': content.get('name'),
                        'version': content.get('version'),
                        'release': content.get('release'),
                        'type': component_type
                    }
                # For remote sources.
                else:
                    component = {
                        'name': content.get('name'),
                        'version': content.get('version'),
                        'type': component_type
                    }
        return component

    async def get_component_data(self, component_link):
        """
        Get component data from the response of component link.
        """
        component = await self.get_component_data_from_corgi(
            component_link)
        if not component:
            # Provide a workaround for Corgi bug:
            # https://issues.redhat.com/browse/PSDEVOPS-3690
            component = self.parse_component_link(component_link)
        return component

    async def get_event_loop(self, component_links):
        """
        Event loop function for component links.
        """
        return await asyncio.gather(*[
            self.get_component_data(component_link)
            for component_link in component_links
        ])

    def get_components_data(self, container_nvr):
        """
        Get the container components data from link.
        If we cannot find component data, will raise an error.
        """
        component_links = self.get_component_links(container_nvr)
        event_loop = asyncio.get_event_loop()
        try:
            components = event_loop.run_until_complete(
                self.get_event_loop(component_links))
            return components
        except Exception as e:
            raise RuntimeError(e) from None
        finally:
            event_loop.close()
