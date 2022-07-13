from django.contrib import admin
from mptt.admin import MPTTModelAdmin
from products.models import (ComponentTreeNode, Product, Release)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    pass


@admin.register(Release)
class ReleaseAdmin(admin.ModelAdmin):
    pass


admin.site.register(ComponentTreeNode, MPTTModelAdmin)
