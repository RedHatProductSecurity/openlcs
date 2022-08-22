from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import (
    GenericForeignKey,
    GenericRelation,
)
import koji

from mptt.models import MPTTModel, TreeForeignKey


class Product(models.Model):
    """Red Hat products"""

    name = models.TextField(unique=True)
    display_name = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    family = models.TextField(blank=True, null=True)

    class Meta:
        app_label = 'products'

    def __str__(self):
        return self.name

    def add_release(self, name, version, notes=""):
        release, _ = self.release_set.update_or_create(
            name=name,
            version=version,
            defaults={
                "notes": notes,
            },
        )
        return release


class Release(models.Model):
    """releases of each product"""

    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    version = models.TextField()
    # 'name' is a joint string: product-version
    name = models.TextField()
    notes = models.TextField(blank=True, null=True)
    release_nodes = GenericRelation(
        "products.ProductTreeNode", related_query_name="release"
    )

    class Meta:
        app_label = 'products'
        unique_together = (('product', 'version'),)
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'version'], name='unique_product_version'
            )
        ]

    def __str__(self):
        return self.name

    def get_or_create_release_node(self):
        ctype = ContentType.objects.get_for_model(self.__class__)
        return ProductTreeNode.objects.get_or_create(
            name=self.name,
            content_type=ctype,
            object_id=self.id,
            # release node will not have a parent.
            parent=None,
        )

    def create_component(self, data):
        from packages.models import Component
        component, _ = Component.objects.get_or_create(**data)
        return component

    def add_components_from_nvrs(self, nvrs, type="SRPM", arch="src"):
        release_node, _ = self.get_or_create_release_node()
        for nvr in nvrs:
            nvr_dict = koji.parse_NVR(nvr)
            # we don't have purl, summary_license based on nvrs.
            component_data = {
                'name': nvr_dict.get('name'),
                'version': nvr_dict.get('version'),
                'release': nvr_dict.get('release'),
                # Unless explicitly specified, we will use default value for
                # `type` and `arch` for components generated from nvrs.
                'type': type,
                'arch': arch,
            }
            component = self.create_component(component_data)
            # attach component to the release_node tree.
            component.release_nodes.get_or_create(
                name=component.name, parent=release_node
            )


class MpttTreeNodeMixin(MPTTModel):
    name = models.TextField()
    parent = TreeForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        abstract = True


class ComponentTreeNode(MpttTreeNodeMixin):
    """Class representing the component tree."""

    def __str__(self):
        return f'{self.content_object.type} node: {self.name}'


class ProductTreeNode(MpttTreeNodeMixin):
    """Class representing the product tree."""

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['parent', 'object_id'],
                name='unique_parent_content_object',
            )
        ]

    def __str__(self):
        if hasattr(self.content_object, 'type'):
            return f'{self.content_object.type} node: {self.name}'
        return f'Product node: {self.name}'
