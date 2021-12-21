from django.contrib import admin
from products.models import Container
from products.models import ContainerPackage
from products.models import Product
from products.models import Release
from products.models import ReleaseContainer
from products.models import ReleasePackage


# Register your models here.
@admin.register(Container)
class ContainerAdmin(admin.ModelAdmin):
    pass


@admin.register(ContainerPackage)
class ContainerPackageAdmin(admin.ModelAdmin):
    pass


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    pass


@admin.register(Release)
class ReleaseAdmin(admin.ModelAdmin):
    pass


@admin.register(ReleaseContainer)
class ReleaseContainerAdmin(admin.ModelAdmin):
    pass


@admin.register(ReleasePackage)
class ReleasePackageAdmin(admin.ModelAdmin):
    pass
