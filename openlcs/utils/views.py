from django.conf import settings
from rest_framework import generics
from rest_framework.response import Response


# Create your views here.
class ObtainConfigView(generics.RetrieveAPIView):
    """
    Return a dict with all config listed in `allowable_attrs`
    from django.conf.settings.
    """

    def get(self, request, *args, **kwargs):

        retval = {}
        allowable_attrs = [
            'SRC_ROOT_DIR',
            'RS_SRC_ROOT_DIR',
            'RS_TYPES',
            'TMP_ROOT_DIR',
            'POST_DIR',
            'KOJI_DOWNLOAD',
            'KOJI_WEBSERVICE',
            'KOJI_WEBURL',
            'SCANCODE_CLI',
            'SCANCODE_LICENSE_SCORE',
            'SCANCODE_TIMEOUT',
            'SCANCODE_PROCESSES',
            'SCANCODE_UNKNOWN_LICENSES',
            'EXTRACTCODE_CLI',
            'LICENSE_DIR',
            'LOGGER_DIR',
            'RETRY_DIR',
            'ORPHAN_CATEGORY',
            'CORGI_API_STAGE',
            'CORGI_API_PROD',
            'TOKEN_SECRET_KEY',
            'REDIS_CACHE_LOCATION',
            'RELEASE_LIST_CACHE_TIMEOUT',
            'RELEASE_RETRIEVE_CACHE_TIMEOUT',
            'LOOKASIDE_CACHE_URL',
            'CONFLUENCE_URL',
            'CONFLUENCE_TOKEN',
            'CONFLUENCE_NAMESPACE',
            'CONFLUENCE_PAGE_TITLE',
        ]
        for attr_name in allowable_attrs:
            attr = getattr(settings, attr_name, None)
            if attr is not None:
                retval[attr_name] = attr

        return Response(data=retval)
