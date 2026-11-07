from django.urls import path

from . import views

app_name = 'accounting'

urlpatterns = [
    path('', views.voucher_list, name='vouchers'),
    path('receipt/', views.receipt_transaction, name='receipt'),
    path('payment/', views.payment_transaction, name='payment'),
    path('cashbook/', views.cashbook_entry, name='cashbook'),
    path('voucher/create/', views.voucher_create, name='voucher_create'),
    path('heads/', views.chart_of_accounts_list, name='heads'),
    path('heads/create/', views.chart_of_accounts_create, name='heads_create'),
    path('heads/<int:pk>/edit/', views.chart_of_accounts_edit, name='heads_edit'),
    path('general-ledger/', views.general_ledger, name='general_ledger'),
    path('day-book/', views.day_book, name='day_book'),
]
