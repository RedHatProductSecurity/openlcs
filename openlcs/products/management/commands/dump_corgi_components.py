import os
import concurrent.futures
import json
import time

import requests
from django.core.management.base import BaseCommand
from django.core.exceptions import ImproperlyConfigured


corgi_api_stage = os.getenv("CORGI_API_STAGE")
corgi_api_prod = os.getenv("CORGI_API_PROD")

CORGI_API_ENDPIONTS = {
    "stage": corgi_api_stage,
    "prod": corgi_api_prod,
}

CORGI_COMPONENT_TYPES = [
    "CONTAINER_IMAGE",
    "GOLANG",
    "MAVEN",
    "NPM",
    "RPM",
    "SRPM",
    "PYPI",
    "UNKNOWN",
    "UPSTREAM",
]


def load_json_from_url(url, session=None):
    if session is None:
        session = session.Session()
    return session.get(url).json()


class Command(BaseCommand):
    help = "Dump corgi components(nested) into json."

    def add_arguments(self, parser):
        parser.add_argument(
            "-e",
            "--env",
            dest="env",
            choices=[
                "stage",
                "prod",
            ],
            default="stage",
            help="stage will be used if unspecified. Requires environment "
            "variables CORGI_API_STAGE and CORGI_API_PROD",
        )
        parser.add_argument(
            "-p",
            "--product-version",
            help="Product version in corgi.",
        )

        parser.add_argument(
            "-n",
            "--num-pages",
            dest="num_pages",
            type=int,
            default=2,
            help="Number of pages to query, 2 by default.",
        )
        parser.add_argument(
            "-t",
            "--component-type",
            dest="component_type",
            choices=CORGI_COMPONENT_TYPES,
            help="Type of component to query.",
        )
        parser.add_argument(
            "-o",
            "--output",
            dest="output",
            default="/tmp/output.json",
            help="json filepath to dump the results into.",
        )

    def get_product_version(self, name, env='stage', fields=None) -> dict:
        endpoint = f"{CORGI_API_ENDPIONTS.get(env)}product_versions"
        params = {'name': name}
        if fields is None:
            fields = ['name', 'ofuri', 'description', 'products', 'components']
        data = requests.get(endpoint, params=params).json()
        # 0 or 1 result for product version name query
        retval = dict()
        if data['count'] > 0:
            version_data = data['results'][0]
            for field in fields:
                retval[field] = version_data[field]
        return retval

    def get_components(self, page: dict, verbosity=1) -> dict:
        """
        Accepts a raw page result json, and returns nested container components
        if there is, along with needed component attributes.
        Returned value follows below form:

            {
                'components': [{'uuid': 'xxx', 'purl': 'xxx', 'provides': []}],
                'errors': [],
            }
        """
        retval = {
            "components": [],
            "errors": [],
        }
        for result in page["results"]:
            component_type = result.get("type")
            if component_type == "CONTAINER_IMAGE":
                container_data = self.get_component_flat(result)
                # deal with container images
                provides = []
                container_provides = result.get("provides")
                links = [c.get("link") for c in container_provides]
                session = requests.Session()
                # too many workers cause corgi api to fail with 500 error
                with concurrent.futures.ThreadPoolExecutor(
                    max_workers=5
                ) as executor:
                    # Start load operations and mark each future with its URL
                    future_to_url = {
                        executor.submit(
                            load_json_from_url, url, session, {}
                        ): url
                        for url in links
                    }
                    for future in concurrent.futures.as_completed(
                        future_to_url
                    ):
                        url = future_to_url[future]
                        try:
                            provides.append(
                                self.get_component_flat(future.result())
                            )
                            if verbosity > 1:
                                self.stdout.write(
                                    self.style.SUCCESS(
                                        f"-- Retrieved component from {url} "
                                        f"provided by "
                                        f"{container_data.get('name')}."
                                    )
                                )
                        except Exception:
                            container_name = container_data.get("name")
                            retval["errors"].append(
                                {
                                    "url": url,
                                    "provided_by": container_name,
                                }
                            )
                            if verbosity > 1:
                                self.stdout.write(
                                    self.style.ERROR(
                                        f"- Failed to retrieve from {url} for"
                                        f"container {container_name}, check "
                                        f"'errors' in output for more details."
                                    )
                                )
                            continue
                container_data["provides"] = provides
                retval["components"].append(container_data)
            else:
                component_data = self.get_component_flat(result)
                retval["components"].append(component_data)
                if verbosity > 1:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Retrieved {component_data['type']} component "
                            f"{component_data['purl']}"
                        )
                    )

        return retval

    def get_component_flat(self, data: dict) -> dict:

        return {
            "uuid": data.get("uuid"),
            "type": data.get("type"),
            "purl": data.get("purl", ""),
            "name": data.get("name"),
            "version": data.get("version"),
            "release": data.get("release", ""),
            "arch": data.get("arch", ""),
            "summary_license": data.get("license", ""),
        }

    # def get_pages(self, url, ctype=None, limit=10, offset=0, num_pages=2):
    def get_pages(self, url, **kwargs):
        params = dict()
        limit = kwargs.get('limit', 10)
        offset = kwargs.get('offset', 0)
        num_pages = kwargs.get('num_pages', 2)
        ctype = kwargs.get('ctype')
        product_version = kwargs.get('product_version')
        if ctype is not None:
            params["type"] = ctype
        if product_version is not None:
            params["product_versions"] = product_version
        session = requests.Session()
        for _ in range(num_pages):
            params.update(
                {
                    "limit": limit,
                    "offset": offset,
                }
            )
            page = session.get(url, params=params).json()
            yield page
            offset += limit

    def handle(self, *args, **options):
        env = options["env"]
        if not CORGI_API_ENDPIONTS.get(env):
            raise ImproperlyConfigured(
                f"Environment variable for corgi " f"{env} not found."
            )
        product_version = options["product_version"]
        product_version_ofuri = None
        version_data = dict()
        if product_version:
            version_data = self.get_product_version(
                name=product_version,
                env=env,
            )
            product_version_ofuri = version_data.get('ofuri')
        endpoint = f"{CORGI_API_ENDPIONTS.get(env)}components"
        num_pages = options["num_pages"]
        output = options["output"]
        ctype = options["component_type"]
        verbosity = options["verbosity"]
        if verbosity > 1:
            counter = time.perf_counter()
        data = dict()
        for page in self.get_pages(
            endpoint,
            ctype=ctype,
            num_pages=num_pages,
            # `product_versions` query unfortunately yields 500s or empty
            # response at times, query using ofuri is more promising.
            product_version=product_version_ofuri
            if product_version_ofuri
            else product_version,
        ):
            components = self.get_components(page, verbosity=verbosity)
            for k, v in components.items():
                data.setdefault(k, []).extend(v)

        if product_version:
            version_data.update(data)
            json_object = json.dumps(version_data, indent=2)
        else:
            json_object = json.dumps(data, indent=2)
        with open(output, "w", encoding='utf-8') as outfile:
            outfile.write(json_object)
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully retrieved {num_pages} page(s) from {endpoint}, "
                f"data saved to {output}!"
            )
        )
        num_errors = len(data.get("errors"))
        if num_errors > 0:
            self.stdout.write(
                self.style.NOTICE(
                    f"Failed to retrieve {num_errors} components, check "
                    f"output file for more details!"
                )
            )
        if verbosity > 1:
            time_elapsed = time.perf_counter() - counter
            self.stdout.write(
                self.style.NOTICE(f"Time elapsed: {time_elapsed}s")
            )
