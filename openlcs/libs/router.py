# coding:utf-8

from collections import OrderedDict

from django.urls import NoReverseMatch
from rest_framework import routers
from rest_framework import views
from rest_framework import reverse
from rest_framework import response


class HybridRouter(routers.DefaultRouter):
    # From http://stackoverflow.com/a/23321478/1459749.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._api_view_urls = {}

    def add_api_view(self, name, url):
        self._api_view_urls[name] = url

    def remove_api_view(self, name):
        del self._api_view_urls[name]

    @property
    def api_view_urls(self):
        ret = {}
        ret.update(self._api_view_urls)
        return ret

    def get_urls(self):
        urls = super().get_urls()
        for api_view_key in self._api_view_urls.keys():
            urls.append(self._api_view_urls[api_view_key])
        return urls

    def get_api_root_view(self, api_urls=None):
        # Code below are mostly from `DefaultRouter` with a few tweaks
        api_root_dict = OrderedDict()
        list_name = self.routes[0].name
        for prefix, _, basename in self.registry:
            api_root_dict[prefix] = list_name.format(basename=basename)
        api_view_urls = self._api_view_urls

        # Code below are from routers.APIRootView
        class APIRootView(views.APIView):
            _ignore_model_permissions = True
            exclude_from_schema = True

            def get(self, request, *args, **kwargs):
                ret = OrderedDict()
                namespace = request.resolver_match.namespace
                for key, url_name in api_root_dict.items():
                    if namespace:
                        url_name = namespace + ':' + url_name
                    try:
                        ret[key] = reverse.reverse(
                            url_name,
                            args=args,
                            kwargs=kwargs,
                            request=request,
                            format=kwargs.get('format', None)
                        )
                    except NoReverseMatch:
                        continue
                # Extend the default APIRootView by adding our own urls.
                for api_view_key in api_view_urls.keys():
                    regex = api_view_urls[api_view_key].pattern.regex
                    if regex.groups == 0:
                        url_name = api_view_urls[api_view_key].name
                        if namespace:
                            url_name = namespace + ':' + url_name
                        ret[api_view_key] = reverse.reverse(
                            url_name,
                            args=args,
                            kwargs=kwargs,
                            request=request,
                            format=kwargs.get('format', None)
                        )
                    else:
                        ret[api_view_key] = "WITH PARAMS: " + regex.pattern
                return response.Response(ret)

        return APIRootView.as_view()

    def register_router(self, router):
        self.registry.extend(router.registry)
        if hasattr(router, "_api_view_urls"):
            self._api_view_urls.update(router._api_view_urls)
