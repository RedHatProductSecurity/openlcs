from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import (
    GenericForeignKey,
    GenericRelation,
)
from datetime import datetime
from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from mptt.models import MPTTModel, TreeForeignKey
from packages.models import Component

import logging
logger = logging.getLogger(__name__)


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


def sync_release_updated_at(*args, sender=None, instance=None, **kwargs):
    release_updated_at = datetime.utcnow()
    logger.info(
        "sync_release_updated_at at: %s (UTC time)", release_updated_at)
    cache.set("release_updated_at", release_updated_at)


post_save.connect(receiver=sync_release_updated_at, sender=Release)
post_delete.connect(receiver=sync_release_updated_at, sender=Release)


class MpttTreeNodeMixin(MPTTModel):
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

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['parent', 'object_id'],
                name='unique_parent_content_object_ct',
            ),
            models.UniqueConstraint(
                fields=['object_id'],
                condition=models.Q(parent=None),
                name='unique_content_object_with_null_parent_ct',
            )
        ]

    def __str__(self):
        return f'{self.content_object.type} node: {self.id}'

    @classmethod
    def _build_component_tree(cls, component_data, parent=None):
        """
        Build component tree node from component data recursively.
        Param `component_data` is a dictionary of (nested) component data.
        If nested components are present, they should be in
        "source_components" key, this is where nested source components are
        collected in corgi.get_source_components module
        When creating component, need to tell if the component_data is from
        component registry or not see`Component.update_or_create_component`
        for more details.
        This should be called only for nested component_data, i.e.,
        "OCI"/"RPMMOD" component. Never call this for a "leaf" component.
        """
        component_ctype = ContentType.objects.get_for_model(Component)
        component_type = component_data['type']
        if component_type in ['OCI', 'RPMMOD']:
            # Handle nested components
            source_components = component_data.pop('source_components', [])
            component = Component.update_or_create_component(component_data)
            component_node, _ = cls.objects.get_or_create(
                parent=parent,
                content_type=component_ctype,
                object_id=component.id,
            )
            for source_component_data in source_components:
                cls._build_component_tree(
                    source_component_data,
                    parent=component_node
                )
            return component_node
        else:
            # rpm/golang/pypi/cargo etc goes here.
            component = Component.update_or_create_component(component_data)
            component_node, _ = cls.objects.get_or_create(
                parent=parent,
                content_type=component_ctype,
                object_id=component.id,
            )
            return component_node

    @classmethod
    def build_component_tree(cls, parent_component, child_component=None):
        """
        Build component tree node from component data.
        Param `parent_component` is a dictionary of (nested) component data.
        If nested components are present, they should be in
        "source_components" key, this is where nested source components are
        collected in corgi.get_source_components module
        param `child_component` is a dict of child component data, key is
        component type, value is component list. If u have a nested
        parent_component param, you can ignore this param
        """
        if parent_component.get('source_components') is None:
            parent_component['source_components'] = list()

        source_components = parent_component['source_components']

        # convert child_component to nested structure
        if child_component:
            for _, components in child_component.items():
                for component in components:
                    source_components.append(component)

        cls._build_component_tree(parent_component)


class ProductTreeNode(MpttTreeNodeMixin):
    """Class representing the product tree."""

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['parent', 'object_id'],
                name='unique_parent_content_object',
            ),
            models.UniqueConstraint(
                fields=['object_id'],
                condition=models.Q(parent=None),
                name='unique_content_object_with_null_parent',
            )
        ]

    @classmethod
    def build_release_node(cls, release_component: dict, product_release: str):
        """
        @params: release_component, component data
        @params: product_release, release name
        Build release tree nodes, each component in a release will be a node,
        for a container/module, the release will be its parent node.
        """
        component_obj = Component.update_or_create_component(release_component)
        release = Release.objects.filter(name=product_release)[0]
        # Create release node
        release_ctype = ContentType.objects.get_for_model(Release)
        release_node, _ = cls.objects.get_or_create(
            content_type=release_ctype,
            object_id=release.id,
            parent=None,
        )

        # Create release component node
        component_obj.release_nodes.get_or_create(
            parent=release_node,
        )

    def __str__(self):
        if hasattr(self.content_object, 'type'):
            return f'{self.content_object.type} node: {self.id}'
        return f'Product node: {self.id}'
