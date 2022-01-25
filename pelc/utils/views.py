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
            'ADHOC_ARCHIVE_SRC_ROOT_DIR',
            'TMP_ROOT_DIR',
            'POST_DIR',
            'BREW_DOWNLOAD',
            'BREW_WEBSERVICE',
            'BREW_WEBURL',
            'SCANCODE_LICENSE_SCORE',
            'SCANCODE_PROCESSES',
            'SCANCODE_CLI',
            'EXTRACTCODE_CLI',
            'LICENSE_DIR',
            'LOGGER_DIR',
            'RETRY_DIR',
            'UMB_ENABLED',
            'UMB_BROKER_URLS',
            'UMB_CI_QUEUE_PREFIX',
            'UMB_CERT_FILE',
            'UMB_KEY_FILE',
            'UMB_CA_CERTS',
            'KBF_CLI',
            'KBF_CONFIG',
            'ORPHAN_CATEGORY',
            'DEPOSIT_URL',
            'DEPOSIT_USER',
            'DEPOSIT_PASSWORD'
        ]
        for attr_name in allowable_attrs:
            attr = getattr(settings, attr_name, None)
            if attr is not None:
                retval[attr_name] = attr

        return Response(data=retval)
