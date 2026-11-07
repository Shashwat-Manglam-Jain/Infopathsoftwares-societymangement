from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.tenants.views import subscription_expired_view, subscription_recharge_view

urlpatterns = [
    path('login', RedirectView.as_view(url='/accounts/login/', permanent=True)),
    path('subscription/expired/', subscription_expired_view, name='subscription_expired'),
    path('subscription/recharge/', subscription_recharge_view, name='subscription_recharge'),
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

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
