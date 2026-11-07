from django.urls import path

from . import views

app_name = 'shares'

urlpatterns = [
    path('', views.share_list, name='list'),
    path('purchase/', views.share_purchase, name='purchase'),
    path('transfer/', views.share_transfer, name='transfer'),
    path('surrender/', views.share_surrender, name='surrender'),
    path('<int:pk>/', views.share_detail, name='detail'),
    path('receipt/<int:txn_id>/', views.ShareReceiptView.as_view(), name='receipt'),
]
