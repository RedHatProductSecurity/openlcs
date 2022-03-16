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
            'TMP_ROOT_DIR',
            'POST_DIR',
            'BREW_DOWNLOAD',
            'BREW_WEBSERVICE',
            'BREW_WEBURL',
            'SCANCODE_CLI',
            'SCANCODE_LICENSE_SCORE',
            'SCANCODE_TIMEOUT',
            'SCANCODE_PROCESSES',
            'EXTRACTCODE_CLI',
            'LICENSE_DIR',
            'LOGGER_DIR',
            'RETRY_DIR',
            'ORPHAN_CATEGORY',
            'DEPOSIT_URL',
            'DEPOSIT_USER',
            'DEPOSIT_PASSWORD',
            'LICENSE_SCANNER',
            'COPYRIGHT_SCANNER'
        ]
        for attr_name in allowable_attrs:
            attr = getattr(settings, attr_name, None)
            if attr is not None:
                retval[attr_name] = attr

        return Response(data=retval)
