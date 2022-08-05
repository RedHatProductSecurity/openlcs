import json

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from packages.models import Component
from products.models import (
    Product,
    Release,
    ComponentTreeNode,
    ProductTreeNode,
)


class Command(BaseCommand):
    help = "Load corgi component data into db"

    def add_arguments(self, parser):
        parser.add_argument(
            "component_data_file",
            help="filepath for corgi component data in json format.",
        )

    def create_product(self, product_name, description=""):
        p, _ = Product.objects.update_or_create(
            name=product_name,
            defaults={
                "description": description,
            },
        )
        return p

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

    def build_release_node(self, data):
        product_version_name = data.get("name")
        description = data.get("description", "")
        product_data = data.get("products")[0]
        product_name = product_data.get('name')
        components = data.get("components")
        product = self.create_product(product_name)
        release = product.add_release(
            name=product_version_name,
            version=product_version_name.split("-")[-1],
            notes=description,
        )
        release_ctype = ContentType.objects.get_for_model(Release)
        release_node, _ = ProductTreeNode.objects.get_or_create(
            name=release.name,
            content_type=release_ctype,
            object_id=release.id,
            parent=None,
        )
        for component_data in components:
            type = component_data.get("type")
            if type == "CONTAINER_IMAGE":
                container_component = self.create_component(component_data)
                cnode, _, = container_component.release_nodes.get_or_create(
                    name=container_component.name,
                    parent=release_node,
                )
                for provided in component_data.get("provides"):
                    component = self.create_component(provided)
                    component.release_nodes.get_or_create(
                        name=component.name,
                        parent=cnode,
                    )
            else:
                component = self.create_component(component_data)
                component.release_nodes.get_or_create(
                    name=component.name, parent=release_node
                )

    def build_container_node(self, data):
        container_component = self.create_component(data)
        component_ctype = ContentType.objects.get_for_model(Component)
        cnode, _ = ComponentTreeNode.objects.get_or_create(
            name=container_component.name,
            content_type=component_ctype,
            object_id=container_component.id,
            parent=None,
        )
        for component_data in data.get("provides", []):
            component = self.create_component(component_data)
            ComponentTreeNode.objects.get_or_create(
                name=component.name,
                parent=cnode,
                content_type=component_ctype,
                object_id=component.id,
            )

    def handle(self, *args, **options):
        data_file = options["component_data_file"]
        with open(data_file, encoding="utf-8") as infile:
            data = json.load(infile)
        if "ofuri" in data:
            self.build_release_node(data)
        else:
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
