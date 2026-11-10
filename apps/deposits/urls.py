from django.urls import path

from . import views

app_name = 'deposits'

urlpatterns = [
    path('fd/', views.fd_list, name='fd_list'),
    path('fd/create/', views.fd_create, name='fd_create'),
    path('fd/<int:pk>/', views.fd_detail, name='fd_detail'),
    path('fd/<int:pk>/premature-close/', views.fd_premature_close, name='fd_premature_close'),
    path('fd/<int:pk>/renew/', views.fd_renew, name='fd_renew'),
    path('rd/', views.rd_list, name='rd_list'),
    path('rd/create/', views.rd_create, name='rd_create'),
    path('rd/<int:pk>/', views.rd_detail, name='rd_detail'),
    path('rd/<int:pk>/collect/', views.rd_collect, name='rd_collect'),
]
