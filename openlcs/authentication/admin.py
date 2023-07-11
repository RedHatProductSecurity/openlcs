from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from authentication.models import RedHatProfile
User = get_user_model()


# Define an inline admin descriptor for Employee model
# which acts a bit like a singleton
class RedHatProfileInline(admin.StackedInline):
    model = RedHatProfile
    can_delete = True
    verbose_name_plural = 'RedHatProfile'
    fk_name = 'user'
    fields = ('sub', 'full_name')


# Define a new User admin
class UserAdmin(BaseUserAdmin):
    inlines = (RedHatProfileInline,)


# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
