from rest_framework import serializers

from products.models import Product, Release
from packages.serializers import (
    ComponentSerializer,
    GroupComponentsSerializer,
)


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
        group_nodes = release_node.get_descendants().filter(
            component__type__in=['OCI', 'RPMMOD']
        )
        # To avoid circular imports
        from packages.models import Component
        group_components = Component.objects.filter(
            id__in=group_nodes.values_list('object_id', flat=True)
        )
        serializer = GroupComponentsSerializer(
            group_components, many=True
        )
        retval.append(serializer.data)
        # Note: `exclude` won't work for reverse generic relations
        # https://code.djangoproject.com/ticket/26261
        other_nodes = release_node.get_descendants().filter(
            component__type__in=[
                "CARGO",
                "GEM",
                "GENERIC",
                "GITHUB",
                "GOLANG",
                "MAVEN",
                "NPM",
                "RPM",
                "PYPI"
            ]
        )
        other_components = Component.objects.filter(
            id__in=other_nodes.values_list('object_id', flat=True)
        )
        serializer = ComponentSerializer(other_components, many=True)
        retval.append(serializer.data)
        return retval
