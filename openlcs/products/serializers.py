from django.conf import settings
from rest_framework import serializers

from packages.models import Component
from packages.serializers import ComponentSerializer
from products.models import Product, Release


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = '__all__'


class ReleaseSerializer(serializers.ModelSerializer):
    """
    Release serializer.
    """

    product = ProductSerializer()
    components = serializers.SerializerMethodField()

    class Meta:
        model = Release
        fields = "__all__"

    def get_components(self, obj):
        retval = list()
        # For releases that have no corresponding node in `tree`, components
        # would be empty
        if not obj.release_nodes.exists():
            return retval
        # There should be only one root node for each release
        release_node = obj.release_nodes.get()
        descendant_nodes = release_node.get_descendants()

        # Add container, module components into release data
        nested_types = ['OCI', 'RPMMOD']
        for component_type in nested_types:
            nodes = descendant_nodes.filter(component__type=component_type)
            components = Component.objects.filter(
                id__in=nodes.values_list('object_id', flat=True)
            )
            serializer = ComponentSerializer(components, many=True)
            retval.append(serializer.data)

        all_types = settings.CORGI_COMPONENT_TYPES
        other_types = [ct for ct in all_types if ct not in nested_types]
        # Note: `exclude` won't work for reverse generic relations
        # https://code.djangoproject.com/ticket/26261
        other_nodes = descendant_nodes.filter(component__type__in=other_types)
        other_components = Component.objects.filter(
            id__in=other_nodes.values_list('object_id', flat=True)
        )
        serializer = ComponentSerializer(other_components, many=True)
        retval.append(serializer.data)
        return retval
