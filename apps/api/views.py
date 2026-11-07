from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.deposits.models import FixedDeposit, RecurringDeposit
from apps.loans.models import EMISchedule, LoanAccount
from apps.members.models import Member
from apps.savings.models import AccountTransaction, SavingsAccount
from apps.shares.models import ShareHolding

from .permissions import IsMemberUser, IsStaffUser
from .serializers import (
    AccountTransactionSerializer,
    EMIScheduleSerializer,
    FixedDepositSerializer,
    LoanAccountSerializer,
    MemberSerializer,
    RecurringDepositSerializer,
    SavingsAccountSerializer,
    ShareHoldingSerializer,
)


def _get_member(user):
    """Get Member linked to this user via email or username match."""
    return (
        Member.objects.filter(
            email=user.email,
            status='active',
        ).first()
        if user.email
        else None
    )


class MemberProfileView(RetrieveAPIView):
    serializer_class = MemberSerializer
    permission_classes = [IsAuthenticated, IsMemberUser]

    def get_object(self):
        return _get_member(self.request.user)


class MemberListView(ListAPIView):
    serializer_class = MemberSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]

    def get_queryset(self):
        qs = Member.objects.filter(status='active')
        branch = self.request.query_params.get('branch')
        if branch:
            qs = qs.filter(branch_id=branch)
        return qs.order_by('member_no')


class MemberDetailView(RetrieveAPIView):
    serializer_class = MemberSerializer
    permission_classes = [IsAuthenticated, IsStaffUser]
    queryset = Member.objects.all()
    lookup_field = 'member_no'


class MySavingsAccountsView(ListAPIView):
    serializer_class = SavingsAccountSerializer
    permission_classes = [IsAuthenticated, IsMemberUser]

    def get_queryset(self):
        member = _get_member(self.request.user)
        if not member:
            return SavingsAccount.objects.none()
        return SavingsAccount.objects.filter(member=member).order_by('account_no')


class MyTransactionsView(ListAPIView):
    serializer_class = AccountTransactionSerializer
    permission_classes = [IsAuthenticated, IsMemberUser]

    def get_queryset(self):
        member = _get_member(self.request.user)
        if not member:
            return AccountTransaction.objects.none()
        return AccountTransaction.objects.filter(
            account__member=member,
        ).order_by('-txn_date', '-created_at')[:100]


class MyLoansView(ListAPIView):
    serializer_class = LoanAccountSerializer
    permission_classes = [IsAuthenticated, IsMemberUser]

    def get_queryset(self):
        member = _get_member(self.request.user)
        if not member:
            return LoanAccount.objects.none()
        return LoanAccount.objects.filter(member=member).order_by('-disbursed_date')


class MyEMIScheduleView(ListAPIView):
    serializer_class = EMIScheduleSerializer
    permission_classes = [IsAuthenticated, IsMemberUser]

    def get_queryset(self):
        loan_id = self.kwargs['loan_id']
        member = _get_member(self.request.user)
        if not member:
            return EMISchedule.objects.none()
        return EMISchedule.objects.filter(
            loan_id=loan_id,
            loan__member=member,
        ).order_by('installment_no')


class MyFixedDepositsView(ListAPIView):
    serializer_class = FixedDepositSerializer
    permission_classes = [IsAuthenticated, IsMemberUser]

    def get_queryset(self):
        member = _get_member(self.request.user)
        if not member:
            return FixedDeposit.objects.none()
        return FixedDeposit.objects.filter(member=member).order_by('-start_date')


class MyRecurringDepositsView(ListAPIView):
    serializer_class = RecurringDepositSerializer
    permission_classes = [IsAuthenticated, IsMemberUser]

    def get_queryset(self):
        member = _get_member(self.request.user)
        if not member:
            return RecurringDeposit.objects.none()
        return RecurringDeposit.objects.filter(member=member).order_by('-start_date')


class MySharesView(ListAPIView):
    serializer_class = ShareHoldingSerializer
    permission_classes = [IsAuthenticated, IsMemberUser]

    def get_queryset(self):
        member = _get_member(self.request.user)
        if not member:
            return ShareHolding.objects.none()
        return ShareHolding.objects.filter(member=member).order_by('-purchase_date')


class MemberDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsMemberUser]

    def get(self, request):
        member = _get_member(request.user)
        if not member:
            return Response({'error': 'No linked member profile'}, status=404)

        savings_balance = SavingsAccount.objects.filter(member=member, status='active').values_list(
            'current_balance', flat=True
        )
        loan_outstanding = LoanAccount.objects.filter(member=member, status='disbursed').values_list(
            'outstanding_principal', flat=True
        )
        fd_total = FixedDeposit.objects.filter(member=member, status='active').values_list('deposit_amount', flat=True)
        rd_total = RecurringDeposit.objects.filter(member=member, status='active').values_list(
            'monthly_installment', flat=True
        )
        shares = ShareHolding.objects.filter(member=member, status='active').values_list('total_amount', flat=True)

        return Response(
            {
                'member_no': member.member_no,
                'name': str(member),
                'total_savings': str(sum(savings_balance)),
                'total_loans_outstanding': str(sum(loan_outstanding)),
                'total_fd': str(sum(fd_total)),
                'total_rd': str(sum(rd_total)),
                'total_shares': str(sum(shares)),
            }
        )
