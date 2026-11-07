from django.urls import path

from apps.tenants.views import SocietySignupView, landing_page

app_name = 'tenants'

urlpatterns = [
    path('', landing_page, name='landing'),
    path('signup/', SocietySignupView.as_view(), name='signup'),
]
