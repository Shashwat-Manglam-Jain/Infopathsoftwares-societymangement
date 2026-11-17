from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

from apps.tenants.views import SocietySignupView, landing_page, public_login

urlpatterns = [
    path('i18n/', include('django.conf.urls.i18n')),
    path('', landing_page, name='landing'),
    path('accounts/login/', public_login, name='public_login'),
    path('signup/', SocietySignupView.as_view(), name='signup'),
    path('terms/', TemplateView.as_view(template_name='legal/terms.html'), name='terms'),
    path('privacy/', TemplateView.as_view(template_name='legal/privacy.html'), name='privacy'),
    path('admin/', admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
