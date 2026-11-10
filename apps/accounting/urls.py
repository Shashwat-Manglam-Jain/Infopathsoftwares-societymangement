from django.urls import path

from . import views

app_name = 'accounting'

urlpatterns = [
    path('', views.voucher_list, name='vouchers'),
    path('receipt/', views.receipt_transaction, name='receipt'),
    path('payment/', views.payment_transaction, name='payment'),
    path('cashbook/', views.cashbook_entry, name='cashbook'),
    path('voucher/create/', views.voucher_create, name='voucher_create'),
    path('voucher/<int:pk>/edit/', views.voucher_edit, name='voucher_edit'),
    path('voucher/<int:pk>/cancel/', views.voucher_cancel, name='voucher_cancel'),
    path('heads/', views.chart_of_accounts_list, name='heads'),
    path('heads/create/', views.chart_of_accounts_create, name='heads_create'),
    path('heads/<int:pk>/edit/', views.chart_of_accounts_edit, name='heads_edit'),
    path('general-ledger/', views.general_ledger, name='general_ledger'),
    path('day-book/', views.day_book, name='day_book'),
    path('interest-master/', views.interest_master_list, name='interest_master'),
    path('interest-master/create/', views.interest_master_create, name='interest_master_create'),
    path('interest-master/<int:pk>/edit/', views.interest_master_edit, name='interest_master_edit'),
    path('cashbook-report/', views.cashbook_report, name='cashbook_report'),
    path('opening-balance/', views.opening_balance_update, name='opening_balance'),
    path('account-search/', views.account_search, name='account_search'),
]
