from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.db.models import F, Sum
from django.shortcuts import redirect, render
from django.views import View

from apps.accounts.permissions import (
    AccountantRequiredMixin,
    AdminRequiredMixin,
    ManagerRequiredMixin,
    accountant_required,
    admin_required,
)

from .models import DayEndLog, FinancialYear, MonthEndLog, WorkingDay


@accountant_required
def dayend_index(request):
    branch = getattr(request, 'current_branch', None)
    if not branch:
        messages.error(request, 'Please select a branch first.')
        return redirect('dashboard:index')

    working_day = WorkingDay.objects.filter(branch=branch).first()
    logs = DayEndLog.objects.filter(branch=branch)[:30]
    month_logs = MonthEndLog.objects.filter(branch=branch)[:12]

    from apps.accounting.models import CashbookMaster

    opening_cash = None
    last_cb = CashbookMaster.objects.filter(branch=branch).order_by('-txn_date').first()
    if last_cb:
        opening_cash = last_cb.closing_balance

    if working_day and not working_day.is_day_open:
        next_working_date = working_day.current_date + timedelta(days=1)
    else:
        next_working_date = date.today()

    last_completed = DayEndLog.objects.filter(
        branch=branch, status='completed',
    ).order_by('-processing_date').first()
    last_completed_date = last_completed.processing_date if last_completed else None

    return render(
        request,
        'dayend/day_end.html',
        {
            'working_day': working_day,
            'logs': logs,
            'month_logs': month_logs,
            'opening_cash': opening_cash,
            'today': date.today(),
            'next_working_date': next_working_date,
            'last_completed_date': last_completed_date,
        },
    )


class BeginDayView(AccountantRequiredMixin, View):
    def post(self, request):
        branch = getattr(request, 'current_branch', None)
        if not branch:
            messages.error(request, 'Please select a branch.')
            return redirect('dayend:index')

        working_day = WorkingDay.objects.filter(branch=branch).first()
        if working_day and not working_day.is_day_open:
            working_date = working_day.current_date + timedelta(days=1)
        else:
            working_date = date.today()

        from .services import begin_working_day

        try:
            wd = begin_working_day(branch, working_date, request.user)
            messages.success(request, f'Working day opened: {wd.current_date}')
        except ValueError as e:
            messages.error(request, str(e))

        return redirect('dayend:index')


class RunDayEndView(AccountantRequiredMixin, View):
    def post(self, request):
        branch = getattr(request, 'current_branch', None)
        if not branch:
            messages.error(request, 'Please select a branch.')
            return redirect('dayend:index')

        from django.db import IntegrityError

        from .services import run_day_end

        try:
            log = run_day_end(branch, request.user)
            messages.success(
                request,
                f'Day End completed for {log.processing_date}. '
                f'Savings: {log.savings_interest_accrued_count}, '
                f'Loans: {log.loan_interest_accrued_count}, '
                f'Overdue: {log.loans_marked_overdue_count}, '
                f'Cashbook: {log.cashbook_entries_posted}',
            )
        except (ValueError, IntegrityError) as e:
            messages.error(request, str(e))

        return redirect('dayend:index')


class RollbackDayEndView(ManagerRequiredMixin, View):
    def post(self, request):
        branch = getattr(request, 'current_branch', None)
        if not branch:
            messages.error(request, 'Please select a branch.')
            return redirect('dayend:index')

        last_completed = DayEndLog.objects.filter(
            branch=branch, status='completed',
        ).order_by('-processing_date').first()
        if not last_completed:
            messages.error(request, 'No completed day end to rollback.')
            return redirect('dayend:index')
        processing_date = last_completed.processing_date

        from .services import rollback_day_end

        try:
            rollback_day_end(branch, processing_date, request.user)
            messages.success(request, f'Day End rolled back for {processing_date}. Day is now open.')
        except ValueError as e:
            messages.error(request, str(e))

        return redirect('dayend:index')


class RunMonthEndView(ManagerRequiredMixin, View):
    def post(self, request):
        branch = getattr(request, 'current_branch', None)
        if not branch:
            messages.error(request, 'Please select a branch.')
            return redirect('dayend:index')

        month_date = date.today().replace(day=1)

        from .services import run_month_end

        try:
            log = run_month_end(branch, month_date, request.user)
            messages.success(
                request,
                f'Month End completed for {month_date.strftime("%b %Y")}. '
                f'Loans: {log.loan_interest_calculated_count}, '
                f'Demand: {log.demand_generated_count}, '
                f'RD Due: {log.rd_installments_due_count}',
            )
        except ValueError as e:
            messages.error(request, str(e))

        return redirect('dayend:index')


class RunYearEndView(AdminRequiredMixin, View):
    def post(self, request):
        branch = getattr(request, 'current_branch', None)
        if not branch:
            messages.error(request, 'Please select a branch.')
            return redirect('dayend:index')

        fy = FinancialYear.objects.filter(is_current=True).first()
        if not fy:
            messages.error(request, 'No current financial year found.')
            return redirect('dayend:index')

        from .services import run_year_end

        try:
            log = run_year_end(branch, fy, request.user)
            profit_loss = 'Profit' if log.profit_or_loss >= 0 else 'Loss'
            messages.success(
                request,
                f'Year End completed for {fy.fy_code}. '
                f'{profit_loss}: ₹{abs(log.profit_or_loss):,.2f}. '
                f'P&L zeroed: {log.pl_accounts_zeroed}',
            )
        except ValueError as e:
            messages.error(request, str(e))

        return redirect('dayend:index')


@admin_required
def reupdate_account_balance(request):
    results = None
    if request.method == 'POST':
        account_type = request.POST.get('account_type', 'savings')
        from_date_str = request.POST.get('from_date', '')
        try:
            from_date = date.fromisoformat(from_date_str)
        except (ValueError, TypeError):
            messages.error(request, 'Invalid date.')
            return render(request, 'dayend/reupdate_balance.html', {})

        results = []
        if account_type == 'savings':
            from apps.savings.models import AccountTransaction, SavingsAccount

            accounts = SavingsAccount.objects.filter(status='active')
            if not request.user.can_access_all_branches:
                accounts = accounts.filter(branch=request.current_branch)
            with transaction.atomic():
                for acct in accounts:
                    txns = AccountTransaction.objects.filter(
                        account=acct,
                        txn_date__gte=from_date,
                    ).order_by('txn_date', 'pk')
                    if not txns.exists():
                        continue
                    prev_txn = (
                        AccountTransaction.objects.filter(
                            account=acct,
                            txn_date__lt=from_date,
                        )
                        .order_by('-txn_date', '-pk')
                        .first()
                    )
                    running = prev_txn.running_balance if prev_txn else Decimal('0')
                    for t in txns:
                        if t.txn_type in ('deposit', 'interest_credit', 'dividend', 'transfer_in'):
                            running += t.amount
                        else:
                            running -= t.amount
                        if t.running_balance != running:
                            t.running_balance = running
                            t.save(update_fields=['running_balance'])
                    old_balance = acct.current_balance
                    if acct.current_balance != running:
                        acct.current_balance = running
                        acct.save(update_fields=['current_balance'])
                        results.append(
                            {
                                'account': acct.account_no,
                                'member': acct.member.name if hasattr(acct, 'member') else '',
                                'old': old_balance,
                                'new': running,
                                'difference': running - old_balance,
                            }
                        )
        elif account_type == 'loan':
            from apps.loans.models import LoanAccount, LoanRepayment

            loans = LoanAccount.objects.filter(status__in=['disbursed', 'npa'])
            if not request.user.can_access_all_branches:
                loans = loans.filter(branch=request.current_branch)
            with transaction.atomic():
                for loan in loans:
                    disbursed = loan.disbursed_amount or loan.approved_amount or Decimal('0')
                    repaid_principal = LoanRepayment.objects.filter(
                        loan=loan,
                        payment_date__gte=from_date,
                    ).aggregate(total=Sum('principal_component', default=Decimal('0')))['total']
                    repaid_before = LoanRepayment.objects.filter(
                        loan=loan,
                        payment_date__lt=from_date,
                    ).aggregate(total=Sum('principal_component', default=Decimal('0')))['total']
                    expected = disbursed - repaid_before - repaid_principal
                    si_total = Decimal('0')
                    if hasattr(loan, 'standing_instructions'):
                        si_total = loan.standing_instructions.aggregate(
                            total=Sum('amount', default=Decimal('0')),
                        )['total']
                    expected += si_total
                    old_balance = loan.outstanding_principal
                    if loan.outstanding_principal != expected:
                        loan.outstanding_principal = expected
                        loan.save(update_fields=['outstanding_principal'])
                        results.append(
                            {
                                'account': loan.loan_no,
                                'member': loan.member.name,
                                'old': old_balance,
                                'new': expected,
                                'difference': expected - old_balance,
                            }
                        )

        messages.success(request, f'{len(results)} accounts corrected.')

    return render(request, 'dayend/reupdate_balance.html', {'results': results})


@admin_required
def reupdate_gl_balance(request):
    from apps.accounting.models import ChartOfAccounts, JournalLine

    results = None
    if request.method == 'POST':
        from_date_str = request.POST.get('from_date', '')
        try:
            from_date = date.fromisoformat(from_date_str)
        except (ValueError, TypeError):
            messages.error(request, 'Invalid date.')
            return render(request, 'dayend/reupdate_gl_balance.html', {})

        results = []
        heads = ChartOfAccounts.objects.filter(is_active=True, allow_transactions=True)
        with transaction.atomic():
            for head in heads:
                agg = JournalLine.objects.filter(
                    account=head,
                    journal_entry__entry_date__gte=from_date,
                    journal_entry__is_reversed=False,
                ).aggregate(
                    total_debit=Sum('debit_amount', default=Decimal('0')),
                    total_credit=Sum('credit_amount', default=Decimal('0')),
                )
                pre_agg = JournalLine.objects.filter(
                    account=head,
                    journal_entry__entry_date__lt=from_date,
                    journal_entry__is_reversed=False,
                ).aggregate(
                    total_debit=Sum('debit_amount', default=Decimal('0')),
                    total_credit=Sum('credit_amount', default=Decimal('0')),
                )
                expected = (
                    head.opening_balance
                    + pre_agg['total_debit']
                    - pre_agg['total_credit']
                    + agg['total_debit']
                    - agg['total_credit']
                )
                old_balance = head.current_balance
                if head.current_balance != expected:
                    head.current_balance = expected
                    head.save(update_fields=['current_balance'])
                    results.append(
                        {
                            'code': head.code,
                            'name': head.name,
                            'old': old_balance,
                            'new': expected,
                            'difference': expected - old_balance,
                        }
                    )

        messages.success(request, f'{len(results)} GL heads corrected.')

    return render(request, 'dayend/reupdate_gl_balance.html', {'results': results})


class InterestCalculateView(AccountantRequiredMixin, View):
    def get(self, request):
        branch = getattr(request, 'current_branch', None)
        if not branch:
            messages.error(request, 'Please select a branch first.')
            return redirect('dashboard:index')

        from apps.savings.models import SavingsAccount

        accounts = SavingsAccount.objects.filter(
            status='active',
            current_balance__gt=0,
            interest_rate__gt=0,
        ).select_related('member', 'branch')

        if not request.user.can_access_all_branches:
            accounts = accounts.filter(branch=branch)

        account_type = request.GET.get('account_type', 'all')
        if account_type != 'all':
            accounts = accounts.filter(account_type=account_type)

        summary = accounts.aggregate(
            total_balance=Sum('current_balance', default=Decimal('0')),
            total_accrued=Sum('accrued_interest', default=Decimal('0')),
        )
        summary['total_accounts'] = accounts.count()

        return render(
            request,
            'dayend/interest_calculate.html',
            {
                'accounts': accounts[:100],
                'summary': summary,
                'calc_date': date.today(),
                'account_type': account_type,
            },
        )

    def post(self, request):
        branch = getattr(request, 'current_branch', None)
        if not branch:
            messages.error(request, 'Please select a branch.')
            return redirect('dayend:interest_calculate')

        from apps.savings.models import SavingsAccount

        calc_date_str = request.POST.get('calc_date', '')
        if calc_date_str:
            from datetime import datetime

            try:
                calc_date = datetime.strptime(calc_date_str, '%Y-%m-%d').date()
            except ValueError:
                calc_date = date.today()
        else:
            calc_date = date.today()

        account_type = request.POST.get('account_type', 'all')

        accounts = SavingsAccount.objects.filter(
            status='active',
            current_balance__gt=0,
            interest_rate__gt=0,
        ).select_related('member', 'branch')

        if not request.user.can_access_all_branches:
            accounts = accounts.filter(branch=branch)

        if account_type != 'all':
            accounts = accounts.filter(account_type=account_type)

        calculated_count = 0
        total_interest = Decimal('0')
        results = []

        with transaction.atomic():
            for acct in accounts:
                daily_interest = (acct.current_balance * acct.interest_rate / 100) / 365
                daily_interest = daily_interest.quantize(Decimal('0.01'))
                acct.accrued_interest = F('accrued_interest') + daily_interest
                acct.last_interest_calculated_date = calc_date
                acct.save(update_fields=['accrued_interest', 'last_interest_calculated_date'])
                calculated_count += 1
                total_interest += daily_interest
                results.append(
                    {
                        'account_no': acct.account_no,
                        'member_name': acct.member.name,
                        'balance': acct.current_balance,
                        'rate': acct.interest_rate,
                        'daily_interest': daily_interest,
                    }
                )

        messages.success(
            request,
            f'Interest calculated for {calculated_count} accounts. Total daily interest: ₹{total_interest:,.2f}',
        )

        accounts_refreshed = SavingsAccount.objects.filter(
            status='active',
            current_balance__gt=0,
            interest_rate__gt=0,
        ).select_related('member', 'branch')
        if not request.user.can_access_all_branches:
            accounts_refreshed = accounts_refreshed.filter(branch=branch)
        if account_type != 'all':
            accounts_refreshed = accounts_refreshed.filter(account_type=account_type)

        summary = accounts_refreshed.aggregate(
            total_balance=Sum('current_balance', default=Decimal('0')),
            total_accrued=Sum('accrued_interest', default=Decimal('0')),
        )
        summary['total_accounts'] = accounts_refreshed.count()

        return render(
            request,
            'dayend/interest_calculate.html',
            {
                'accounts': accounts_refreshed[:100],
                'summary': summary,
                'calc_date': calc_date,
                'account_type': account_type,
                'results': results,
                'calculated_count': calculated_count,
                'total_interest': total_interest,
            },
        )


class InterestPostView(ManagerRequiredMixin, View):
    def get(self, request):
        branch = getattr(request, 'current_branch', None)
        if not branch:
            messages.error(request, 'Please select a branch first.')
            return redirect('dashboard:index')

        from apps.savings.models import SavingsAccount

        accounts = SavingsAccount.objects.filter(
            status='active',
            accrued_interest__gt=0,
        ).select_related('member', 'branch')

        if not request.user.can_access_all_branches:
            accounts = accounts.filter(branch=branch)

        accounts = accounts.annotate(
            balance_after_post=F('current_balance') + F('accrued_interest'),
        )

        summary = accounts.aggregate(
            total_accrued=Sum('accrued_interest', default=Decimal('0')),
        )
        summary['total_accounts'] = accounts.count()

        return render(
            request,
            'dayend/interest_post.html',
            {
                'accounts': accounts[:100],
                'summary': summary,
                'post_date': date.today(),
            },
        )

    def post(self, request):
        branch = getattr(request, 'current_branch', None)
        if not branch:
            messages.error(request, 'Please select a branch.')
            return redirect('dayend:interest_post')

        from apps.savings.models import AccountTransaction, SavingsAccount

        post_date = date.today()
        post_date_str = request.POST.get('post_date', '')
        if post_date_str:
            from datetime import datetime

            try:
                post_date = datetime.strptime(post_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        accounts = SavingsAccount.objects.filter(
            status='active',
            accrued_interest__gt=0,
        ).select_related('member', 'branch')

        if not request.user.can_access_all_branches:
            accounts = accounts.filter(branch=branch)

        posted_count = 0
        total_posted = Decimal('0')

        with transaction.atomic():
            for acct in accounts:
                interest_amount = acct.accrued_interest
                if interest_amount <= 0:
                    continue

                acct.current_balance += interest_amount
                acct.interest_charged += interest_amount
                acct.accrued_interest = Decimal('0')
                acct.last_interest_posted_date = post_date
                acct.save(
                    update_fields=[
                        'current_balance',
                        'interest_charged',
                        'accrued_interest',
                        'last_interest_posted_date',
                    ]
                )

                AccountTransaction.objects.create(
                    account=acct,
                    branch=acct.branch,
                    txn_date=post_date,
                    value_date=post_date,
                    txn_type='interest_credit',
                    amount=interest_amount,
                    running_balance=acct.current_balance,
                    narration=f'Interest credited for period ending {post_date}',
                    payment_mode='transfer',
                    created_by=request.user,
                )

                posted_count += 1
                total_posted += interest_amount

        messages.success(
            request,
            f'Interest posted to {posted_count} accounts. Total posted: ₹{total_posted:,.2f}',
        )

        return redirect('dayend:interest_post')
