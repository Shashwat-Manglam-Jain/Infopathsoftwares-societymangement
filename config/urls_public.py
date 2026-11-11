from django.contrib import admin
from django.urls import path

from apps.tenants.views import SocietySignupView, landing_page, public_login

urlpatterns = [
    path('', landing_page, name='landing'),
    path('accounts/login/', public_login, name='public_login'),
    path('signup/', SocietySignupView.as_view(), name='signup'),
    path('admin/', admin.site.urls),
]
