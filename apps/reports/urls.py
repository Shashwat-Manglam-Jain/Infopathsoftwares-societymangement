from django.urls import path

from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.report_index, name='index'),
    path('trial-balance/', views.trial_balance, name='trial_balance'),
    path('profit-loss/', views.profit_loss, name='profit_loss'),
    path('balance-sheet/', views.balance_sheet, name='balance_sheet'),
    path('personal-ledger/', views.personal_ledger, name='personal_ledger'),
    path('cashbook/', views.cashbook_report, name='cashbook_report'),
]
