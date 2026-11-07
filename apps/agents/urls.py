from django.urls import path

from . import views

app_name = 'agents'

urlpatterns = [
    path('', views.agent_list, name='list'),
    path('create/', views.agent_create, name='create'),
    path('<int:pk>/', views.agent_detail, name='detail'),
    path('pigmmy/', views.pigmmy_account_list, name='pigmmy_list'),
    path('pigmmy/create/', views.pigmmy_create, name='pigmmy_create'),
    path('pigmmy/<int:pk>/', views.pigmmy_detail, name='pigmmy_detail'),
    path('collections/', views.collection_list, name='collection_list'),
    path('collections/create/', views.collection_create, name='collection_create'),
]
