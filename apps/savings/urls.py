from django.urls import path

from . import views

app_name = 'savings'

urlpatterns = [
    path('', views.savings_list, name='list'),
    path('create/', views.savings_create, name='create'),
    path('<int:pk>/', views.savings_detail, name='detail'),
    path('<int:pk>/edit/', views.savings_edit, name='edit'),
    path('<int:pk>/deposit/', views.savings_deposit, name='deposit'),
    path('<int:pk>/withdraw/', views.savings_withdraw, name='withdraw'),
    path('<int:pk>/statement/', views.savings_statement, name='statement'),
    path('<int:pk>/change-status/', views.savings_change_status, name='change_status'),
    path('receipt/<int:txn_id>/', views.DepositReceiptView.as_view(), name='receipt'),
    path('passbook/<int:account_id>/', views.PassbookPrintView.as_view(), name='passbook'),
    path('api/account-type-rate/', views.account_type_rate_api, name='account_type_rate_api'),
]
