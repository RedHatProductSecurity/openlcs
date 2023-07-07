import logging
import django_filters
import jwt
import time

from mozilla_django_oidc.views import OIDCAuthenticationCallbackView

from django.contrib.auth import get_user_model
from django.http import JsonResponse
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet
from rest_framework.views import APIView

from authentication.serializers import UserSerializer
from authentication.mixins import GetAutobotTokenMixin

User = get_user_model()
logger = logging.getLogger(__name__)


class TokenViewSet(ModelViewSet):
    """
    ## REST API Auth ##

    We use `TokenAuthentication` for API Authentication.

    Unauthenticated user will not be able to access to APIs.

    **WARNING:** Please do not share your token with anyone else.

    **NOTE:** It's highly recommended to make sure your API is only
    available over `https` when using `TokenAuthentication`.

    We use DjangoModelPermissions for RESTful API permissions.

    Authorization will only be granted if the user is authenticated
    and has the relevant model permissions assigned.

    * __POST__ requests require the user to have the `add` permission
    on the model.
    * __PUT__ and __PATCH__ requests require the user to have the `change`
    permission on the model.
    * __DELETE__ requests require the user to have the `delete` permission
    on the model.

    ### Using Token

    * Obtain token

        You can only get your token when clink /rest/v1/auth, \
"Extra Actions", "Obtain token" after you login to the system.

        you will get a `Response` like:

            {"token": "00bf04e8187f6e6d54f510515e8bde88e5bb7904"}

    * Then you should add one HTTP HEADER with this token in this format with
    every request need authentication:

            Authorization: Token 00bf04e8187f6e6d54f510515e8bde88e5bb7904

        For curl, it would be:

            curl -H "Content-Type: application/json" \
-H 'Authorization: Token 00bf04e8187f6e6d54f510515e8bde88e5bb7904' \
-X GET %(HOST_NAME)s/%(API_PATH)s/{RESOURCE_URL}/

        Replace the {RESOURCE_URL} with the exact resource you'd like to visit.

    * In case you want to refresh your token, you can do it with:

            curl -k --negotiate -u : -H "Content-Type: application/json" \
-H 'Authorization: Token 00bf04e8187f6e6d54f510515e8bde88e5bb7904' \
%(HOST_NAME)s/%(API_PATH)s/auth/refresh_token/

        Or you can get the new token when clink /rest/v1/auth, \
"Extra Actions", "Refresh token" after you login to the system.

        you will get a `Response` with refreshed token:

            {"token": "092p04e8187f6e6d53f510515e8bde88e5bb7258"}

    """

    permission_classes = [IsAuthenticated]
    queryset = Token.objects.all()

    def list(self, request):
        return Response()

    @action(detail=False)
    def obtain_token(self, request, pk=None):
        """
        ### Obtain Token

        __URL__:
        /obtain_token/

        __EXAMPLE__:

        Run:

            curl -k --negotiate -u : -H "Content-Type: application/json"
            %(HOST_NAME)s/%(API_PATH)s/auth/obtain_token/

        you will get a `Response` like:

            {"token": "00bf04e8187f6e6d54f510515e8bde88e5bb7904"}
        """
        if request.user.is_authenticated:
            if request.user.is_active:
                token, _ = Token.objects.get_or_create(user=request.user)
                return Response({'token': token.key})
            else:
                reason = {"Obtain Token Error": "You're not an active user."}
                return Response(reason, status=401)
        else:
            reason = {"Obtain Token Error": "Failed to authenticate."}
            return Response(reason, status=401)

    @action(detail=False, methods=['get', 'put'])
    def refresh_token(self, request):
        """
        ### Refresh Token

        __URL__:
        /refresh_token/

        __EXAMPLE__:

        Run:
            curl -k --negotiate -u : -X PUT -H "Content-Type: application/json"
            %(HOST_NAME)s/%(API_PATH)s/auth/refresh_token/

        you will get a `Response` with refreshed token:

            {"token": "00bf04e8187f6e6d54f510515e8bde88e5bb7904"}
        """
        if request.user.is_authenticated:
            if request.user.is_active:
                try:
                    token = Token.objects.get(user=request.user)
                    token.delete()
                except Token.DoesNotExist:
                    reason = {
                        "Refresh Token Error":
                        "You have not got a token yet, please obtain first."
                    }
                    return Response(reason, status=400)
                token = Token.objects.create(user=request.user)
                return Response({'token': token.key})
            else:
                reason = {"Refresh Token Error": "You're not an active user."}
                return Response(reason, status=401)
        else:
            reason = {"Refresh Token Error": "Authenticate Failed."}
            return Response(reason, status=401)


class GetAutobotToken(APIView, GetAutobotTokenMixin):
    def get(self, request):
        try:
            access_token = self.get_access_token()
            user = self.get_or_create_user(access_token)
            token, _ = Token.objects.get_or_create(user=user)
        except jwt.ExpiredSignatureError as e:
            # Handle expired token error
            return JsonResponse({'error': f'Access token has expired: {e}'},
                                status=401)
        except jwt.DecodeError as e:
            # Handle invalid token or other JWT-related errors
            return JsonResponse({'error': f'Invalid access token: {e}'},
                                status=401)
        except RuntimeError as e:
            return JsonResponse({'error': f"{e}"}, status=401)
        return Response({'token': token.key})


class UserFilter(django_filters.FilterSet):
    # https://django-filter.readthedocs.io/en/stable/guide/migration.html?highlight=MethodFilter#methodfilter-and-filter-action-replaced-by-filter-method-382  # noqa
    manager = django_filters.CharFilter(method='filter_manager')

    class Meta:
        model = User
        fields = {'username': ['exact', 'contains']}

    def filter_manager(self, queryset, value):
        return queryset.filter(profile__manager__username=value)


class UserViewSet(ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    filter_class = UserFilter

    def list(self, request, *args, **kwargs):
        """
        ####__Request__####

            curl -X GET -H "Content-Type: application/json" \
%(HOST_NAME)s/%(API_PATH)s/users/

        ####__Supported query params__####

        ``username``: String, kerberos username of the user.

        ``username__contains``: String, kerberos username substring to search.

        ``manager``: String, kerberos username of the manager.

        ####__Response__####

            HTTP 200 OK
            Content-Type: application/json

            {
                "count": 11021,
                "next": "%(HOST_NAME)s/%(API_PATH)s/users/?page=2",
                "previous": null,
                "results": [
                    {
                        "username": "lmandvek",
                        "email": "lmandvek@redhat.com",
                        "realname": "Lokesh Mandvekar",
                        "manager": "pthomas",
                    },
                    ...
                ]
            }
        """
        return super(UserViewSet, self).list(request, *args, **kwargs)


class CustomOIDCAuthenticationCallbackView(OIDCAuthenticationCallbackView):
    """
    This class used to fix login simultaneous issue.
    """
    def get(self, request):
        time.sleep(1)
        return super().get(request)
