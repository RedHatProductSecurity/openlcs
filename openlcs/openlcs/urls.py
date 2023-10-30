"""
OpenLCS URL Configuration

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

from mozilla_django_oidc.views import OIDCAuthenticationRequestView

from authentication import views as auth_views
from libs.router import HybridRouter
from packages import views as package_views
from products import views as product_views
from reports import views as report_views
from rest_framework.authtoken import views as token_views
from tasks import views as task_views
from utils.views import ObtainConfigView

DRF_ROOT = os.path.join(settings.DRF_NAMESPACE, settings.DRF_API_VERSION)

# Default router where ModelViewSet resides
router = HybridRouter()
router.register(r'auth', auth_views.TokenViewSet, basename='auth')
router.register(r'components', package_views.ComponentViewSet,
                basename='components')
router.register(r'crontabschedule', package_views.CrontabScheduleViewSet,
                basename='crontabschedule')
router.register(r'files', package_views.FileViewSet, basename='files')
router.register(r'paths', package_views.PathViewSet, basename='paths')
router.register(r'periodictask', package_views.PeriodicTaskViewSet,
                basename='periodictask')
router.register(r'releases', product_views.ReleaseViewSet, basename='releases')
router.register(r'sources', package_views.SourceViewSet, basename='sources')
router.register(r'subscriptions', package_views.ComponentSubscriptionViewSet,
                basename='subscriptions')
router.register(r'missingcomponents', package_views.MissingComponentViewSet,
                basename='missingcomponents')
router.register(r'tasks', task_views.TaskViewSet, basename='tasks')
router.register(r'licensedetections', report_views.LicenseDetectionViewSet,
                basename='licensedetections')
router.register(r'copyrightdetections', report_views.CopyrightDetectionViewSet,
                basename='copyrightdetections')
router.register(r'reportmetrics', report_views.ReportMetricsViewSet,
                basename='reportmetrics')

# Router where APIView resides
additional_router = HybridRouter()
additional_router.add_api_view(r'manifest parser', path(
    'manifest_parser/', product_views.ManifestFileParserView.as_view(),
    name='manifest_parser_view'))

main_router = HybridRouter()
main_router.register_router(router)
main_router.register_router(additional_router)

app_name = 'openlcs'

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
    path(f'{DRF_ROOT}/check_source_status/',
         package_views.CheckSourceStatus.as_view(),
         name='check_source_status'),
    path(f'{DRF_ROOT}/save_component_with_source/',
         package_views.SaveComponentWithSource.as_view(),
         name='save_component_with_source'),
    path(f'{DRF_ROOT}/delete_success_component_from_missing/',
         package_views.DeleteSuccessComponentFromMissing.as_view(),
         name='delete_success_component_from_missing'),
    path(f'{DRF_ROOT}/check_duplicate_import/',
         package_views.CheckDuplicateImport.as_view(),
         name='check_duplicate_import'),
    path(f'{DRF_ROOT}/savecomponents/',
         package_views.SaveComponentsView.as_view(),
         name='save_group_components'),
    path(f'{DRF_ROOT}/obtain_config/',
         ObtainConfigView.as_view(), name='obtain_config'),
    path(f'{DRF_ROOT}/get_autobot_token/',
         auth_views.GetAutobotToken.as_view(),
         name='get_autobot_token')
]

if settings.OIDC_AUTH_ENABLED:
    urlpatterns.extend([
        path("oidc/", include("mozilla_django_oidc.urls")),
        path('oidc/login/',
             OIDCAuthenticationRequestView.as_view(),
             name='oidc_login')
    ])

if settings.DEBUG:
    # To load static files in django , added this part
    # https://docs.djangoproject.com/en/3.2/ref/contrib/staticfiles/
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns
    urlpatterns += staticfiles_urlpatterns()
