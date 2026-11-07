from django.urls import path

from . import views

app_name = 'notifications'

urlpatterns = [
    path('templates/', views.NotificationTemplateListView.as_view(), name='template_list'),
    path('templates/<int:pk>/edit/', views.NotificationTemplateUpdateView.as_view(), name='template_edit'),
    path('sms-log/', views.SMSLogListView.as_view(), name='sms_log'),
    path('send-bulk/', views.SendBulkSMSView.as_view(), name='send_bulk'),
]
