from django.urls import path

from . import views

app_name = 'agents'

urlpatterns = [
    path('', views.agent_list, name='list'),
    path('create/', views.agent_create, name='create'),
    path('<int:pk>/', views.agent_detail, name='detail'),
    path('<int:pk>/client-sheet/', views.agent_client_sheet, name='agent_client_sheet'),
    path('pigmmy/', views.pigmmy_account_list, name='pigmmy_list'),
    path('pigmmy/create/', views.pigmmy_create, name='pigmmy_create'),
    path('pigmmy/<int:pk>/', views.pigmmy_detail, name='pigmmy_detail'),
    path('collections/', views.collection_list, name='collection_list'),
    path('collections/create/', views.collection_create, name='collection_create'),
    path('collections/posting/', views.collection_posting_list, name='collection_posting'),
    path('collections/<int:pk>/post/', views.collection_post, name='collection_post'),
    path('api/agent-clients/<int:agent_id>/', views.agent_clients_api, name='agent_clients_api'),
    path('api/member-accounts/<int:member_id>/', views.member_accounts_api, name='member_accounts_api'),
]
