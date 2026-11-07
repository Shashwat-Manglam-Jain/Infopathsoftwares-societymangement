from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .authentication import SocietyTokenObtainPairView
from .views import (
    MemberDashboardView,
    MemberDetailView,
    MemberListView,
    MemberProfileView,
    MyEMIScheduleView,
    MyFixedDepositsView,
    MyLoansView,
    MyRecurringDepositsView,
    MySavingsAccountsView,
    MySharesView,
    MyTransactionsView,
)

app_name = 'api'

urlpatterns = [
    # Auth
    path('token/', SocietyTokenObtainPairView.as_view(), name='token_obtain'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    # Member self-service
    path('me/', MemberProfileView.as_view(), name='my_profile'),
    path('me/dashboard/', MemberDashboardView.as_view(), name='my_dashboard'),
    path('me/savings/', MySavingsAccountsView.as_view(), name='my_savings'),
    path('me/transactions/', MyTransactionsView.as_view(), name='my_transactions'),
    path('me/loans/', MyLoansView.as_view(), name='my_loans'),
    path('me/loans/<int:loan_id>/emi/', MyEMIScheduleView.as_view(), name='my_emi_schedule'),
    path('me/fixed-deposits/', MyFixedDepositsView.as_view(), name='my_fds'),
    path('me/recurring-deposits/', MyRecurringDepositsView.as_view(), name='my_rds'),
    path('me/shares/', MySharesView.as_view(), name='my_shares'),
    # Staff endpoints
    path('members/', MemberListView.as_view(), name='member_list'),
    path('members/<str:member_number>/', MemberDetailView.as_view(), name='member_detail'),
]
