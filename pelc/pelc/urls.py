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
import os

from django.conf import settings
from django.conf.urls import include
from django.contrib import admin
from django.urls import path
from rest_framework.authtoken import views as token_views

from authentication import views as auth_views
from packages import views as package_views
from reports import views as report_views
from tasks import views as task_views
from libs.router import HybridRouter

from utils.views import ObtainConfigView

DRF_ROOT = os.path.join(settings.DRF_NAMESPACE, settings.DRF_API_VERSION)

# Default router where ModelViewSet resides
router = HybridRouter()
router.register(r'auth', auth_views.TokenViewSet, basename='auth')
router.register(r'files', package_views.FileViewSet, basename='files')
router.register(r'sources', package_views.SourceViewSet, basename='sources')
router.register(r'paths', package_views.PathViewSet, basename='paths')
router.register(r'packages', package_views.PackageViewSet, basename='packages')
router.register(r'licensedetections', report_views.LicenseDetectionViewSet,
                basename='licensedetections')
router.register(r'copyrightdetections', report_views.CopyrightDetectionViewSet,
                basename='copyrightdetections')
router.register(r'tasks', task_views.TaskViewSet, basename='tasks')

# Router where APIView resides
additional_router = HybridRouter()
additional_router.add_api_view(r'manifest parser', path(
    'manifest_parser/',
    package_views.ManifestFileParserView.as_view(),
    name='manifest_parser_view'))

main_router = HybridRouter()
main_router.register_router(router)
main_router.register_router(additional_router)

urlpatterns = [
    path(f'{DRF_ROOT}/obtain_token_local/',
         token_views.obtain_auth_token),
    path(f'{DRF_ROOT}/api-auth/',
         include('rest_framework.urls', namespace='rest_framework')),
    path(f'{DRF_ROOT}/', include(main_router.urls)),
    path('admin/', admin.site.urls),
    path(f'{DRF_ROOT}/packageimporttransaction/',
         package_views.PackageImportTransactionView.as_view(),
         name='package_import_transaction'),
    path(f'{DRF_ROOT}/savescanresult/',
         package_views.SaveScanResultView.as_view(),
         name='save_scan_result'),
    path(f'{DRF_ROOT}/check_duplicate_files/',
         package_views.CheckDuplicateFiles.as_view(),
         name='check_duplicate_files'),
    path(f'{DRF_ROOT}/check_duplicate_source/',
         package_views.CheckDuplicateSource.as_view(),
         name='check_duplicate_source'),
    path(f'{DRF_ROOT}/obtain_config/',
         ObtainConfigView.as_view(), name='obtain_config'),
]

if settings.DEBUG:
    # To load static files in django , added this part
    # https://docs.djangoproject.com/en/3.2/ref/contrib/staticfiles/
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns
    urlpatterns += staticfiles_urlpatterns()
