from django.core.management.base import BaseCommand, CommandError
from django.contrib.contenttypes.models import ContentType

import json
from products.models import ComponentTreeNode
from packages.models import Component


class Command(BaseCommand):
    help = "Load corgi component data into db"

    def add_arguments(self, parser):
        parser.add_argument(
            "component_data_file",
            help="filepath for corgi component data in json format.",
        )

    def create_component(self, data):
        component, _ = Component.objects.update_or_create(
            uuid=data.get("uuid"),
            type=data.get("type"),
            name=data.get("name"),
            version=data.get("version"),
            release=data.get("release"),
            arch=data.get("arch"),
            defaults={
                "purl": data.get("purl"),
                "summary_license": data.get("license"),
            },
        )
        return component

    def build_container_node(self, data):
        container_component = self.create_component(data)
        component_ctype = ContentType.objects.get_for_model(Component)
        container_node, _ = ComponentTreeNode.objects.get_or_create(
            name=container_component.name,
            content_type=component_ctype,
            object_id=container_component.id,
        )
        for component_data in data.get("provides", []):
            component = self.create_component(component_data)
            ComponentTreeNode.objects.get_or_create(
                name=component.name,
                parent=container_node,
                content_type=component_ctype,
                object_id=component.id,
            )

    def handle(self, *args, **options):
        data_file = options["component_data_file"]
        data = None
        with open(data_file, encoding="utf-8") as infile:
            data = json.load(infile)
        components = data["components"]
        for component in components:
            if component.get("type") == "CONTAINER_IMAGE":
                self.build_container_node(component)
            # FIXME: deal with RHEL_MODULE properly.
            # This `elif` is probably not needed, as similar with container
            # image, "RHEL_MODULE" also consist of nested components.
            elif component.get("type") == "RHEL_MODULE":
                continue
            else:
                self.create_component(component)
        self.stdout.write(
            self.style.SUCCESS(f"Successfully loaded {data_file}!")
        )
