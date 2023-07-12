import jwt
import os
import requests

from requests.exceptions import RequestException, HTTPError

from django.conf import settings
from django.contrib.auth import get_user_model
User = get_user_model()

USER_OIDC_CLIENT_ID = os.getenv("USER_OIDC_CLIENT_ID", "")
USER_OIDC_CLIENT_SECRET = os.getenv("USER_OIDC_CLIENT_SECRET", "")
OIDC_OP_TOKEN_ENDPOINT = os.getenv("OIDC_AUTH_URI") + '/token'
OIDC_OP_USER_ENDPOINT = os.getenv("OIDC_AUTH_URI") + '/userinfo'


class GetAutobotTokenMixin:
    def get_or_create_user(self, access_token):
        """
        Get or create a user according the access token.
        """
        claims = self.decode_access_token(access_token)
        user, status = User.objects.get_or_create(
            username=claims.get('preferred_username'),
            first_name=claims.get('given_name'),
            last_name=claims.get('family_name'),
            email=claims.get('email')
        )

        # Set user permission.
        if claims.get('preferred_username') in settings.OPENLCS_ADMIN_LIST:
            user.is_staff = True
            user.is_superuser = True
        user.save()

        if status:
            # Create a Red Hat Profile for this user
            redhat_profile = user.redhatprofile
            redhat_profile.sub = claims.get('sub')
            redhat_profile.full_name = claims.get('name')
            redhat_profile.save()
        return user

    @staticmethod
    def get_access_token():
        """
        Get access token according user client id and secret.
        """
        try:
            response = requests.post(
                OIDC_OP_TOKEN_ENDPOINT,
                auth=(USER_OIDC_CLIENT_ID, USER_OIDC_CLIENT_SECRET),
                data={"grant_type": "client_credentials"},
                timeout=30
            )
            response.raise_for_status()
            response_data = response.json()

            access_token = f"{response_data['access_token']}"
        except (RequestException, HTTPError) as e:
            err_msg = f'Failed to get access token key. Reason: {e}'
            raise RuntimeError(err_msg) from None
        return access_token

    @staticmethod
    def decode_access_token(encoded_jwt):
        """
        Decode the access token to get the user information.
        """
        key = """{"typ":"JWT", "alg":"RS256"}"""  # noqa
        return jwt.decode(encoded_jwt, key,
                          options={"verify_signature": False})
