from django.core.management.base import BaseCommand, CommandError

# from polls.models import Question as Poll

import time
import concurrent.futures
import json
import requests


def load_json_from_url(session, url, params={}):
    return session.get(url, params=params).json()


def get_components(page: dict) -> dict:
    """
    Accepts a raw page result json, and returns nested container components
    if there is, along with needed component attributes.
    Returned value follows below form:

        {
            'containers': [{'uuid': 'xxx', 'purl': 'xxx', 'provides': []}],
            'others': [{'uuid': 'xxx, 'purl': 'xxx'}],
            'errors': [],
        }
    """
    retval = {
        "containers": [],
        "others": [],
        "errors": [],
    }
    for result in page["results"]:
        component_type = result.get("type")
        if component_type == "CONTAINER_IMAGE":
            container_data = get_component_flat(result)
            # deal with container images
            provides = []
            container_provides = result.get("provides")
            links = [c.get("link") for c in container_provides]
            session = requests.Session()
            # too many workers cause corgi api to fail with 500 error
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=5
            ) as executor:
                # Start the load operations and mark each future with its URL
                future_to_url = {
                    executor.submit(load_json_from_url, session, url, {}): url
                    for url in links
                }
                for future in concurrent.futures.as_completed(future_to_url):
                    url = future_to_url[future]
                    try:
                        provides.append(get_component_flat(future.result()))
                    except Exception as exc:
                        retval["errors"].append(url)
                        # print('%r generated an exception: %s' % (url, exc))
                        continue
            container_data["provides"] = provides
            retval["containers"].append(container_data)
        else:
            retval["others"].append(get_component_flat(result))

    return retval


def get_component_flat(data: dict) -> dict:

    return {
        "uuid": data.get("uuid"),
        "type": data.get("type"),
        "purl": data.get("purl", ""),
        "name": data.get("name"),
        "version": data.get("version"),
        "release": data.get("release", ""),
        "arch": data.get("arch", ""),
        "license": data.get("license", ""),
    }


class Command(BaseCommand):
    help = "Dump corgi components(nested) into json."

    def add_arguments(self, parser):
        parser.add_argument(
            "--corgi-component-url",
            dest="url",
            default="https://corgi-stage.prodsec.redhat.com/api/v1/components",
            help="corgi-stage will be used if unspecified.",
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
            choices=[
                "CONTAINER_IAMGE",
                "GOLANG",
                "MAVEN",
                "NPM",
                "RPM",
                "SRPM",
                "PYPI",
                "UNKNOWN",
                "UPSTREAM",
            ],
            help="Type of component to query.",
        )
        parser.add_argument(
            "-o",
            "--output",
            dest="output",
            default="/tmp/output.json",
            help="json filepath to dump the results into.",
        )

    def get_pages(
        self, url, component_type=None, limit=10, offset=0, num_pages=2
    ):
        params = dict()
        if component_type is not None:
            params["type"] = component_type
        session = requests.Session()
        for p in range(num_pages):
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
        url = options["url"]
        num_pages = options["num_pages"]
        # Use temporary filepath if output is unspecified.
        output = options["output"]
        component_type = options["component_type"]
        verbosity = options["verbosity"]
        if verbosity > 1:
            counter = time.perf_counter()
        data = dict()
        for page in self.get_pages(
            url, component_type=component_type, num_pages=num_pages
        ):
            components = get_components(page)
            for k, v in components.items():
                data.setdefault(k, []).extend(v)

        json_object = json.dumps(data, indent=2)
        with open(output, "w") as outfile:
            outfile.write(json_object)
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully retrieved {num_pages} page(s) from {url}, "
                f"data saved to {output}!"
            )
        )
        if verbosity > 1:
            time_elapsed = time.perf_counter() - counter
            self.stdout.write(
                self.style.NOTICE(f"Time elapsed: {time_elapsed}s")
            )
