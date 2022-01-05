#
# Copyright (c) 2015 Red Hat
# Licensed under The MIT License (MIT)
# http://opensource.org/licenses/MIT
#
from collections import OrderedDict

from django.conf import settings
from django.utils.encoding import smart_text

from rest_framework.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN
from rest_framework.renderers import BrowsableAPIRenderer
from rest_framework.utils import formatting


APIROOT_DOC = """
The REST APIs make it possible to programmatic access the data in PELC.

The REST API identifies users using Token which will be generated
for all authenticated users.

**Please remember to use your token as HTTP header for every requests
that need authentication.**

Responses are available in JSON format.

"""


class ReadOnlyBrowsableAPIRenderer(BrowsableAPIRenderer):
    template = "browsable_api/api.html"
    methods_mapping = (
        'list',
        'retrieve',
        'create',
        'update',
        'destroy',
        'partial_update',
        'compare',
        'retry',
        'rescan',
        'bulk_create_files',
        'bulk_create_paths'
    )

    def get_raw_data_form(self, data, view, method, request):
        return None

    def get_rendered_html_form(self, data, view, method, request):
        return None

    def get_context(self, data, accepted_media_type, renderer_context):
        context = super(ReadOnlyBrowsableAPIRenderer, self).get_context(
            data,
            accepted_media_type,
            renderer_context
        )

        if context is not None:
            context['display_edit_forms'] = False
            context['version'] = "1.0"
            view = renderer_context['view']
            context['overview'] = self.get_overview(view)

        return context

    def get_overview(self, view):
        if view.__class__.__name__ == 'APIRootView':
            return self.format_docstring(APIROOT_DOC)
        overview = view.__doc__ or ''
        return self.format_docstring(overview)

    def get_description(self, view, status_code=None):

        if status_code in (HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN):
            return ''

        if view.__class__.__name__ == 'APIRootView':
            return ''

        description = OrderedDict()
        for method in self.methods_mapping:
            func = getattr(view, method, None)
            docstring = func and func.__doc__ or ''
            if docstring:
                description[method] = self.format_docstring(docstring)

        return description

    def format_docstring(self, docstring):
        formatted = docstring % settings.BROWSABLE_DOCUMENT_MACROS
        string = formatting.dedent(smart_text(formatted))
        return formatting.markup_description(string)
