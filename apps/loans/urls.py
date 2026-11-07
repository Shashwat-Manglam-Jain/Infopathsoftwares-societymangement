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
    path('receipt/<int:repayment_id>/', views.EMIReceiptView.as_view(), name='emi_receipt'),
    path('products/', views.loan_product_list, name='product_list'),
    path('products/create/', views.loan_product_create, name='product_create'),
    path('products/<int:pk>/edit/', views.loan_product_edit, name='product_edit'),
]
