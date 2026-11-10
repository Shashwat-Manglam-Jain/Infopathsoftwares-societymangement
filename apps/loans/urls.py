from django.urls import path

from . import views

app_name = 'loans'

urlpatterns = [
    path('', views.loan_list, name='list'),
    path('apply/', views.loan_apply, name='apply'),
    path('<int:pk>/', views.loan_detail, name='detail'),
    path('<int:pk>/approve/', views.loan_approve, name='approve'),
    path('<int:pk>/disburse/', views.loan_disburse, name='disburse'),
    path('<int:pk>/collect/', views.loan_collect, name='collect'),
    path('loan-charges/', views.loan_charge_list, name='loan_charge_list'),
    path('loan-charges/create/', views.loan_charge_create, name='loan_charge_create'),
    path('receipt/<int:repayment_id>/', views.EMIReceiptView.as_view(), name='emi_receipt'),
    path('<int:loan_pk>/guarantors/add/', views.guarantor_add, name='guarantor_add'),
    path('guarantors/<int:pk>/edit/', views.guarantor_edit, name='guarantor_edit'),
    path('guarantors/<int:pk>/delete/', views.guarantor_delete, name='guarantor_delete'),
    path('products/', views.loan_product_list, name='product_list'),
    path('products/create/', views.loan_product_create, name='product_create'),
    path('products/<int:pk>/edit/', views.loan_product_edit, name='product_edit'),
]
