from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth import middleware
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponseRedirect
from django.urls import reverse
User = get_user_model()


class AuthRequiredMiddleware(middleware.AuthenticationMiddleware):

    def process_request(self, request):
        # AuthenticationMiddleware is required so that request.user exists.
        if not hasattr(request, 'user'):
            raise ImproperlyConfigured(
                "The Django remote user auth middleware requires the"
                " authentication middleware to be installed.  Edit your"
                " MIDDLEWARE setting to insert"
                " 'django.contrib.auth.middleware.AuthenticationMiddleware'"
                " before the RemoteUserMiddleware class.")

        # Only requests from browsers need to log in, API use token
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        if 'Mozilla' not in user_agent:
            return
        # Avoid redirects to login loop.
        for path in ['/oidc/login/', '/oidc/callback/']:
            if request.META.get("PATH_INFO").startswith(path):
                return
        if not bool(request.user and request.user.is_authenticated):
            if 'openlcs' in settings.HOSTNAME:
                return HttpResponseRedirect(reverse('oidc_login'))
