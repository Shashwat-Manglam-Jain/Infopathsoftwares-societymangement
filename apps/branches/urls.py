from django.urls import path

from . import views

app_name = 'branches'

urlpatterns = [
    path('', views.branch_list, name='list'),
    path('create/', views.branch_create, name='create'),
    path('<int:pk>/edit/', views.branch_edit, name='edit'),
    path('switch/<int:branch_id>/', views.switch_branch, name='switch'),
]
