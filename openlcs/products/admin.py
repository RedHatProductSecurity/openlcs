from django.contrib import admin
from mptt.admin import MPTTModelAdmin

from products.models import Container
from products.models import ContainerPackage
from products.models import Product
from products.models import Release
from products.models import ReleaseContainer
from products.models import ReleasePackage
from products.models import ComponentTreeNode


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
class ComponentTreeNodeAdmin(admin.ModelAdmin):
    pass
