"""pelc2 URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls import include
from django.contrib import admin
from django.urls import path, re_path
from rest_framework.authtoken import views as token_views
from rest_framework import routers

from authentication import views as auth_views


router = routers.DefaultRouter()
router.register(r'auth', auth_views.TokenViewSet)

DRF_NAMESPACE = settings.DRF_NAMESPACE
DRF_API_VERSION = settings.DRF_API_VERSION

urlpatterns = [
    re_path(r'^%s/%s/obtain_token_local/' % (DRF_NAMESPACE, DRF_API_VERSION),
            token_views.obtain_auth_token),
    re_path(r'^%s/%s/api-auth' % (DRF_NAMESPACE, DRF_API_VERSION),
            include('rest_framework.urls', namespace='rest_framework')),
    re_path(r'^%s/%s/' % (DRF_NAMESPACE, DRF_API_VERSION),
            include(router.urls)),

    path('admin/', admin.site.urls),
]
