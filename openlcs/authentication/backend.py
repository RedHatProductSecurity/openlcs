import logging
import os
from typing import Any
from urllib.parse import urlparse, urlunparse

from django.contrib.auth import get_user_model
from mozilla_django_oidc.auth import OIDCAuthenticationBackend

from authentication.models import RedHatProfile

User = get_user_model()
logger = logging.getLogger(__name__)

USERS_KEYS = [
    'sub',
    'preferred_username',
    'name',
    'given_name',
    'family_name',
    'email'
]


# Code reference from Corgi:
# https://github.com/RedHatProductSecurity/component-registry/blob/main/corgi/core/authentication.py#L15 # noqa
class OpenLCSOIDCBackend(OIDCAuthenticationBackend):
    """
    An extension of mozilla_django_oidc's authentication backend
    which customizes user creation and authentication to support Red
    Hat SSO additional claims.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(args, kwargs)
        self.token_info = None

    def verify_claims(self, claims: Any) -> bool:
        """
        Require, at a minimum, that a user have a sub attribute in claim
        before even trying to authenticate them.
        """
        verified = super(OpenLCSOIDCBackend, self).verify_claims(claims)
        return verified and "sub" in claims

    def filter_users_by_claims(self, claims):
        """
        The default behavior is to use e-mail, which may not be unique.
        Instead, we use Red Hat UUID, which should be unique and persistent
        between changes to other user claims.
        """
        # Since verify_claims requires sub in claims, it will always be
        # here.
        sub = claims["sub"]
        try:
            rhat_profile = RedHatProfile.objects.get(sub=sub)
            return [rhat_profile.user]
        except RedHatProfile.DoesNotExist:
            logger.info("UUID %s doesn't have a RedHatProfile", sub)
        return self.UserModel.objects.none()

    def create_user(self, claims: Any) -> User:
        """
        Rather than changing the existing Django user model, this stores
        Red Hat SSO claims in a separate model keyed to the created user.
        """
        # Get user information
        user_detail = [claims.get(key) for key in USERS_KEYS]

        # Create the user.
        user = User.objects.create(
            username=user_detail[1],
            first_name=user_detail[3],
            last_name=user_detail[4],
            email=user_detail[5]
        )

        # Set user permission.
        if user_detail[1] in os.getenv("OPENLCS_ADMIN_LIST"):
            user.is_staff = True
            user.is_superuser = True
        user.save()

        # Create a Red Hat Profile for this user
        redhat_profile = user.redhatprofile
        redhat_profile.sub = user_detail[0]
        redhat_profile.full_name = user_detail[2]
        redhat_profile.save()

        return user

    def update_user(self, user: User, claims: Any) -> User:
        """
        Update user settings.
        """
        RedHatProfile.objects.filter(user=user).update(
            sub=claims.get("sub", ""),
            full_name=claims.get("name", ""),
        )
        return user

    @staticmethod
    def is_local_url(url):
        parsed_url = urlparse(url)
        return parsed_url.hostname in ('127.0.0.1', 'localhost')

    @staticmethod
    def replace_non_local_url_with_https(url):
        parsed_url = urlparse(url)
        parsed_url = parsed_url._replace(scheme='https')
        return urlunparse(parsed_url)

    def get_token(self, payload):
        redirect_uri = payload.get("redirect_uri")
        if not self.is_local_url(redirect_uri):
            redirect_uri = self.replace_non_local_url_with_https(redirect_uri)
            payload['redirect_uri'] = redirect_uri
        return super(OpenLCSOIDCBackend, self).get_token(payload)
