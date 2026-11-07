from django.urls import path

from . import views

app_name = 'members'

urlpatterns = [
    path('', views.member_list, name='list'),
    path('new/', views.member_create, name='create'),
    path('<int:pk>/', views.member_detail, name='detail'),
    path('<int:pk>/edit/', views.member_edit, name='edit'),
    path('<int:pk>/upload-document/', views.member_document_upload, name='upload_document'),
    path('import/', views.MemberImportView.as_view(), name='import'),
    path('import/template/', views.SampleImportTemplateView.as_view(), name='import_template'),
    path('export/', views.MemberExportView.as_view(), name='export'),
]
