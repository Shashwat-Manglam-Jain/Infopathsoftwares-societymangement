from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.views.generic import TemplateView


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        branch = getattr(self.request, 'current_branch', None)
        today = date.today()

        context['setup_progress'] = self._get_setup_progress()

        from apps.deposits.models import FixedDeposit, RecurringDeposit
        from apps.loans.models import LoanAccount, LoanRepayment
        from apps.members.models import Member
        from apps.savings.models import AccountTransaction, SavingsAccount
        from apps.shares.models import ShareHolding

        member_qs = Member.objects.filter(status='active')
        savings_qs = SavingsAccount.objects.filter(status='active')
        loan_qs = LoanAccount.objects.filter(status='disbursed')
        fd_qs = FixedDeposit.objects.filter(status='active')
        rd_qs = RecurringDeposit.objects.filter(status='active')
        share_qs = ShareHolding.objects.filter(status='active')

        user = self.request.user
        if branch and not user.can_access_all_branches:
            member_qs = member_qs.filter(branch=branch)
            savings_qs = savings_qs.filter(branch=branch)
            loan_qs = loan_qs.filter(branch=branch)
            fd_qs = fd_qs.filter(branch=branch)
            rd_qs = rd_qs.filter(branch=branch)
            share_qs = share_qs.filter(branch=branch)

        context['total_members'] = member_qs.count()
        total_savings = savings_qs.aggregate(total=Sum('current_balance'))['total'] or Decimal('0')
        total_fd = fd_qs.aggregate(total=Sum('deposit_amount'))['total'] or Decimal('0')
        context['total_savings'] = total_savings
        context['total_fd'] = total_fd
        context['total_rd'] = rd_qs.count()
        context['total_deposits'] = total_savings + total_fd
        context['total_loans'] = loan_qs.aggregate(total=Sum('outstanding_principal'))['total'] or Decimal('0')
        context['total_shares'] = share_qs.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')

        context['overdue_count'] = loan_qs.filter(overdue_days__gt=0).count()
        context['npa_count'] = LoanAccount.objects.filter(status='npa').count()
        context['pending_approvals'] = LoanAccount.objects.filter(status='applied').count()
        context['fd_maturing_soon'] = fd_qs.filter(maturity_date__lte=today + timedelta(days=30)).count()

        today_txn = AccountTransaction.objects.filter(txn_date=today)
        today_repay = LoanRepayment.objects.filter(payment_date=today)
        if branch and not user.can_access_all_branches:
            today_txn = today_txn.filter(branch=branch)
            today_repay = today_repay.filter(branch=branch)

        context['today_deposits'] = today_txn.filter(txn_type='deposit').aggregate(total=Sum('amount'))[
            'total'
        ] or Decimal('0')
        context['today_withdrawals'] = today_txn.filter(txn_type='withdrawal').aggregate(total=Sum('amount'))[
            'total'
        ] or Decimal('0')
        context['today_emi'] = today_repay.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        context['today_txn_count'] = today_txn.count()

        context['recent_transactions'] = AccountTransaction.objects.select_related(
            'account__member', 'branch'
        ).order_by('-created_at')[:5]

        context['today'] = today

        tenant = getattr(self.request, 'tenant', None)
        if tenant:
            try:
                context['subscription'] = tenant.subscription
            except Exception:
                context['subscription'] = None
        else:
            context['subscription'] = None

        return context

    def _get_setup_progress(self):
        from apps.accounts.models import CustomUser
        from apps.branches.models import Branch
        from apps.loans.models import LoanProduct
        from apps.members.models import Member
        from apps.savings.models import SavingsAccount
        from apps.shares.models import ShareConfig

        steps = []

        branch_count = Branch.objects.count()
        steps.append(
            {
                'name': 'Add Branches',
                'description': 'Add your head office and sub-branches',
                'done': branch_count >= 1,
                'count': branch_count,
                'url': '/branches/',
                'icon': 'building',
            }
        )

        user_count = CustomUser.objects.filter(is_active=True).exclude(role='member').count()
        steps.append(
            {
                'name': 'Add Staff Users',
                'description': 'Add cashiers, managers, and accountants',
                'done': user_count >= 2,
                'count': user_count,
                'url': '/accounts/staff/',
                'icon': 'users',
            }
        )

        member_count = Member.objects.filter(status='active').count()
        steps.append(
            {
                'name': 'Add Members',
                'description': 'Register your society members (or import from Excel)',
                'done': member_count >= 1,
                'count': member_count,
                'url': '/members/',
                'icon': 'user-plus',
            }
        )

        has_shares = ShareConfig.objects.exists()
        steps.append(
            {
                'name': 'Configure Shares',
                'description': 'Set share face value and limits',
                'done': has_shares,
                'url': '/shares/',
                'icon': 'file-text',
            }
        )

        product_count = LoanProduct.objects.filter(is_active=True).count()
        steps.append(
            {
                'name': 'Setup Loan Products',
                'description': 'Configure loan types with interest rates',
                'done': product_count >= 1,
                'count': product_count,
                'url': '/loans/',
                'icon': 'credit-card',
            }
        )

        account_count = SavingsAccount.objects.count()
        steps.append(
            {
                'name': 'Open Savings Accounts',
                'description': 'Open savings accounts for members',
                'done': account_count >= 1,
                'count': account_count,
                'url': '/savings/',
                'icon': 'wallet',
            }
        )

        completed = sum(1 for s in steps if s['done'])
        total = len(steps)
        progress_percent = int((completed / total) * 100) if total > 0 else 0

        return {
            'steps': steps,
            'completed': completed,
            'total': total,
            'percent': progress_percent,
            'all_done': completed == total,
        }
