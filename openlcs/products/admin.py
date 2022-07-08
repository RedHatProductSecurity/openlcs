from django.contrib import admin
from mptt.admin import MPTTModelAdmin
from products.models import (ComponentTreeNode, Container, ContainerPackage,
                             Product, Release, ReleaseContainer,
                             ReleasePackage)


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
    list_display = ('release', 'package_nvr', 'is_source')
    search_fields = ['release__name', 'package_nvr']


admin.site.register(ComponentTreeNode, MPTTModelAdmin)
