from django.db import models
from packages.models import Package


class Container(models.Model):
    """
    containers that we know about; be cautious about ever allowing
    these to be deleted since this action silently removes containers
    from a release
    """
    reference = models.TextField(unique=True)

    class Meta:
        db_table = 'container'


class ContainerPackage(models.Model):
    """packages in each container"""
    container = models.ForeignKey('Container')
    package_nvr = models.TextField()
    source = models.SmallIntegerField()

    class Meta:
        db_table = 'container_package'
        unique_together = (('container', 'package_nvr'),)


class Product(models.Model):
    """Red Hat products"""
    name = models.TextField(unique=True)
    description = models.TextField(blank=True, null=True)
    displayname = models.TextField(blank=True, null=True)
    family = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'product'


class Release(models.Model):
    """releases of each product"""
    product = models.ForeignKey(Product)
    version = models.TextField()
    notes = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'release'
        unique_together = (('product', 'version'),)


class ReleaseContainer(models.Model):
    """containers as part of a release"""
    release = models.ForeignKey(Release)
    container = models.ForeignKey(Container)

    class Meta:
        db_table = 'release_container'
        unique_together = (('release', 'container'),)


class ReleasePackage(models.Model):
    """packages within each release"""
    release = models.ForeignKey('Release')
    # FIXME: need to be consistent with definition from Package
    package_nvr = models.TextField()
    source = models.SmallIntegerField()

    class Meta:
        db_table = 'release_package'
        unique_together = (('release', 'package_nvr'),)
