from django.db import models


class Container(models.Model):
    """
    containers that we know about; be cautious about ever allowing
    these to be deleted since this action silently removes containers
    from a release
    """
    reference = models.TextField(unique=True)

    class Meta:
        app_label = 'products'

    def __str__(self):
        return self.reference


class ContainerPackage(models.Model):
    """packages in each container"""
    container = models.ForeignKey(
        Container,
        on_delete=models.CASCADE
    )
    package_nvr = models.TextField()
    source = models.SmallIntegerField()

    class Meta:
        app_label = 'products'
        constraints = [
            models.UniqueConstraint(
                fields=['container', 'package_nvr'],
                name='unique_container_package')
        ]

    def __str__(self):
        return "%s-%s" % (self.container, self.package_nvr)


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


class Release(models.Model):
    """releases of each product"""
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE
    )
    version = models.TextField()
    # 'name' is a joint string: product-version
    name = models.TextField()
    notes = models.TextField(blank=True, null=True)

    class Meta:
        app_label = 'products'
        unique_together = (('product', 'version'),)
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'version'],
                name='unique_product_version')
        ]

    def __str__(self):
        return self.name


class ReleaseContainer(models.Model):
    """containers as part of a release"""
    release = models.ForeignKey(
        Release,
        on_delete=models.CASCADE
    )
    container = models.ForeignKey(
        Container,
        on_delete=models.RESTRICT
    )

    class Meta:
        app_label = 'products'
        constraints = [
            models.UniqueConstraint(
                fields=['release', 'container'],
                name='unique_release_container')
        ]

    def __str__(self):
        return "%s-%s" % (self.release, self.container)


class ReleasePackage(models.Model):
    """packages within each release"""
    release = models.ForeignKey(
        Release,
        on_delete=models.CASCADE
    )
    package_nvr = models.TextField()
    source = models.SmallIntegerField()

    class Meta:
        app_label = 'products'
        constraints = [
            models.UniqueConstraint(
                fields=['release', 'package_nvr'],
                name='unique_release_package_nvr')
        ]

    def __str__(self):
        return "%s-%s" % (self.release, self.package_nvr)
