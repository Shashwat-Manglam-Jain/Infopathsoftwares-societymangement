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
    path('deposit-reports/', views.deposit_reports, name='deposit_reports'),
    path('loan-reports/', views.loan_reports, name='loan_reports'),
    path('balance-reports/', views.balance_reports, name='balance_reports'),
    path('enquiry/', views.enquiry, name='enquiry'),
    path('pigmmy-reports/', views.pigmmy_reports, name='pigmmy_reports'),
    path('notices/', views.notices, name='notices'),
    path('calculator/', views.calculator, name='calculator'),
]
