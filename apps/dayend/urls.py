from django.urls import path

from . import views

app_name = 'dayend'

urlpatterns = [
    path('', views.dayend_index, name='index'),
    path('begin-day/', views.BeginDayView.as_view(), name='begin_day'),
    path('run-dayend/', views.RunDayEndView.as_view(), name='run_dayend'),
    path('rollback/', views.RollbackDayEndView.as_view(), name='rollback'),
    path('month-end/', views.RunMonthEndView.as_view(), name='month_end'),
    path('year-end/', views.RunYearEndView.as_view(), name='year_end'),
    path('reupdate-balance/', views.reupdate_account_balance, name='reupdate_balance'),
    path('reupdate-gl-balance/', views.reupdate_gl_balance, name='reupdate_gl_balance'),
    path('interest-calculate/', views.InterestCalculateView.as_view(), name='interest_calculate'),
    path('interest-post/', views.InterestPostView.as_view(), name='interest_post'),
]
