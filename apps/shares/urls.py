from django.urls import path

from . import views

app_name = 'shares'

urlpatterns = [
    path('', views.share_list, name='list'),
    path('purchase/', views.share_purchase, name='purchase'),
    path('transfer/', views.share_transfer, name='transfer'),
    path('surrender/', views.share_surrender, name='surrender'),
    path('config/', views.share_config_list, name='config_list'),
    path('config/create/', views.share_config_create, name='config_create'),
    path('config/<int:pk>/edit/', views.share_config_edit, name='config_edit'),
    path('config/<int:pk>/toggle/', views.share_config_toggle, name='config_toggle'),
    path('<int:pk>/', views.share_detail, name='detail'),
    path('receipt/<int:txn_id>/', views.ShareReceiptView.as_view(), name='receipt'),
]
