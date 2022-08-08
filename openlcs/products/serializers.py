from rest_framework import serializers

from products.models import Product, Release
from products.models import ReleasePackage
from packages.serializers import (
    ComponentSerializer,
    ContainerComponentsSerializer,
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
        # There should be only one root node for each release
        release_node = obj.release_nodes.get()
        retval = list()
        container_nodes = release_node.get_descendants().filter(
            component__type='CONTAINER_IMAGE'
        )
        from packages.models import Component

        container_components = Component.objects.filter(
            id__in=container_nodes.values_list('object_id', flat=True)
        )
        serializer = ContainerComponentsSerializer(
            container_components, many=True, context={'for_release': True}
        )
        retval.append(serializer.data)
        # FIXME: rhel module build
        # Note: `exclude` won't work for reverse generic relations
        # https://code.djangoproject.com/ticket/26261
        other_nodes = release_node.get_descendants().filter(
            component__type__in=[
                'RPM',
                'SRPM',
                'GOLANG',
                'NPM',
                'PYPI',
                'MAVEN',
            ]
        )
        other_components = Component.objects.filter(
            id__in=other_nodes.values_list('object_id', flat=True)
        )
        serializer = ComponentSerializer(other_components, many=True)
        retval.append(serializer.data)
        return retval


class ReleasePackageSerializer(serializers.ModelSerializer):

    scan_result = serializers.SerializerMethodField()

    class Meta:
        model = ReleasePackage
        exclude = (
            'id',
            'release',
        )

    def get_scan_result(self, obj):
        return obj.get_scan_result()
