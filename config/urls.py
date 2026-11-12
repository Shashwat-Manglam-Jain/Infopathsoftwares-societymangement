from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.core.views import avatar_view, error_403, error_404, error_500
from apps.tenants.views import society_detail, society_edit, subscription_expired_view, subscription_recharge_view

urlpatterns = [
    path('i18n/', include('django.conf.urls.i18n')),
    path('avatar/<str:name>/<int:size>/', avatar_view, name='avatar'),
    path('login', RedirectView.as_view(url='/accounts/login/', permanent=True)),
    path('subscription/expired/', subscription_expired_view, name='subscription_expired'),
    path('subscription/recharge/', subscription_recharge_view, name='subscription_recharge'),
    path('society/', society_detail, name='society_detail'),
    path('society/edit/', society_edit, name='society_edit'),
    path('admin/', admin.site.urls),
    path('', include('apps.dashboard.urls')),
    path('branches/', include('apps.branches.urls')),
    path('accounts/', include('apps.accounts.urls')),
    path('members/', include('apps.members.urls')),
    path('shares/', include('apps.shares.urls')),
    path('savings/', include('apps.savings.urls')),
    path('loans/', include('apps.loans.urls')),
    path('deposits/', include('apps.deposits.urls')),
    path('agents/', include('apps.agents.urls')),
    path('accounting/', include('apps.accounting.urls')),
    path('dayend/', include('apps.dayend.urls')),
    path('reports/', include('apps.reports.urls')),
    path('audit/', include('apps.audit.urls')),
    path('notifications/', include('apps.notifications.urls')),
    # API
    path('api/', include('apps.api.urls')),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]

handler403 = error_403
handler404 = error_404
handler500 = error_500

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
