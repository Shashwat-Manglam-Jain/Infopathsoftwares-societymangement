from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.db.models import F, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.accounts.permissions import (
    AccountantRequiredMixin,
    AdminRequiredMixin,
    ManagerRequiredMixin,
    accountant_required,
    admin_required,
    day_open_required,
    manager_required,
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

    last_completed = (
        DayEndLog.objects.filter(
            branch=branch,
            status='completed',
        )
        .order_by('-processing_date')
        .first()
    )
    last_completed_date = last_completed.processing_date if last_completed else None

    current_month = date.today().replace(day=1)
    month_end_done = MonthEndLog.objects.filter(
        branch=branch, month=current_month, status='completed',
    ).exists()

    branch_statuses = None
    if request.user.can_access_all_branches:
        from apps.branches.models import Branch

        branches = Branch.objects.filter(status='active').order_by('-is_head_office', 'branch_name')
        statuses = []
        for b in branches:
            wd = WorkingDay.objects.filter(branch=b).first()
            me_done = MonthEndLog.objects.filter(branch=b, month=current_month, status='completed').exists()
            last_dayend = DayEndLog.objects.filter(branch=b, status='completed').order_by('-processing_date').first()
            statuses.append({
                'branch': b,
                'working_day': wd,
                'is_day_open': wd.is_day_open if wd else False,
                'day_end_completed': wd.day_end_completed if wd else False,
                'current_date': wd.current_date if wd else None,
                'last_dayend_date': last_dayend.processing_date if last_dayend else None,
                'month_end_done': me_done,
            })
        branch_statuses = statuses

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
            'month_end_done': month_end_done,
            'branch_statuses': branch_statuses,
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
            from apps.audit.services import log_action

            log_action(
                user=request.user, branch=branch, action='create',
                table_name='WorkingDay', record_id=wd.pk,
                new_values={'current_date': str(wd.current_date), 'is_day_open': True},
                ip_address=request.META.get('REMOTE_ADDR'),
            )
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
            from apps.audit.services import log_action

            log_action(
                user=request.user, branch=branch, action='approve',
                table_name='DayEndLog', record_id=log.pk,
                new_values={
                    'processing_date': str(log.processing_date),
                    'savings_interest': log.savings_interest_accrued_count,
                    'loan_interest': log.loan_interest_accrued_count,
                    'cashbook_entries': log.cashbook_entries_posted,
                },
                ip_address=request.META.get('REMOTE_ADDR'),
            )
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

        last_completed = (
            DayEndLog.objects.filter(
                branch=branch,
                status='completed',
            )
            .order_by('-processing_date')
            .first()
        )
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
@day_open_required
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
@day_open_required
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
                totals = JournalLine.objects.filter(
                    gl_account=head,
                    journal_entry__is_reversed=False,
                ).aggregate(
                    total_debit=Sum('debit_amount', default=Decimal('0')),
                    total_credit=Sum('credit_amount', default=Decimal('0')),
                )
                total_dr = totals['total_debit']
                total_cr = totals['total_credit']
                if head.account_group in ('asset', 'expense'):
                    expected = head.opening_balance + total_dr - total_cr
                else:
                    expected = head.opening_balance + total_cr - total_dr
                old_balance = head.current_balance
                changed = (
                    head.current_balance != expected
                    or head.debit_balance != total_dr
                    or head.credit_balance != total_cr
                )
                if changed:
                    head.current_balance = expected
                    head.debit_balance = total_dr
                    head.credit_balance = total_cr
                    head.save(update_fields=['current_balance', 'debit_balance', 'credit_balance'])
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
    def _get_accounts(self, request, branch, account_type='all'):
        from apps.deposits.models import FixedDeposit, RecurringDeposit
        from apps.loans.models import LoanAccount
        from apps.savings.models import SavingsAccount

        rows = []
        branch_filter = {} if request.user.can_access_all_branches else {'branch': branch}

        if account_type in ('all', 'savings', 'current', 'security'):
            sb_qs = SavingsAccount.objects.filter(
                status='active', current_balance__gt=0, interest_rate__gt=0, **branch_filter,
            ).select_related('member', 'branch')
            if account_type in ('savings', 'current', 'security'):
                sb_qs = sb_qs.filter(account_type=account_type)
            for a in sb_qs:
                rows.append({
                    'account_no': a.account_no, 'member_name': a.member.name,
                    'member_id': a.member_id, 'account_id': a.pk,
                    'balance': a.current_balance, 'rate': a.interest_rate,
                    'accrued': a.accrued_interest, 'account_type': f'SB-{a.get_account_type_display()}',
                    'category': 'savings', 'obj': a,
                    'last_calc_date': a.last_interest_calculated_date,
                    'last_post_date': a.last_interest_posted_date,
                })

        if account_type in ('all', 'fd'):
            fd_qs = FixedDeposit.objects.filter(
                status='active', interest_rate__gt=0, **branch_filter,
            ).select_related('member', 'branch')
            for fd in fd_qs:
                rows.append({
                    'account_no': fd.fd_no, 'member_name': fd.member.name,
                    'member_id': fd.member_id, 'account_id': fd.pk,
                    'balance': fd.deposit_amount, 'rate': fd.interest_rate,
                    'accrued': fd.accrued_interest, 'account_type': 'Fixed Deposit',
                    'category': 'fd', 'obj': fd,
                    'last_calc_date': fd.last_interest_calculated_date,
                    'last_post_date': fd.last_interest_posted_date,
                })

        if account_type in ('all', 'rd'):
            rd_qs = RecurringDeposit.objects.filter(
                status='active', interest_rate__gt=0, **branch_filter,
            ).select_related('member', 'branch')
            for rd in rd_qs:
                from apps.deposits.models import RDInstallment
                paid = RDInstallment.objects.filter(rd=rd, status='paid').aggregate(
                    total=Sum('amount', default=Decimal('0')),
                )['total']
                if paid > 0:
                    rows.append({
                        'account_no': rd.rd_no, 'member_name': rd.member.name,
                        'member_id': rd.member_id, 'account_id': rd.pk,
                        'balance': paid, 'rate': rd.interest_rate,
                        'accrued': Decimal('0'), 'account_type': 'Recurring Deposit',
                        'category': 'rd', 'obj': rd,
                        'last_calc_date': None, 'last_post_date': None,
                    })

        if account_type in ('all', 'loan'):
            loan_qs = LoanAccount.objects.filter(
                status='disbursed', interest_rate__gt=0, outstanding_principal__gt=0, **branch_filter,
            ).select_related('member', 'branch')
            for loan in loan_qs:
                rows.append({
                    'account_no': loan.loan_no, 'member_name': loan.member.name,
                    'member_id': loan.member_id, 'account_id': loan.pk,
                    'balance': loan.outstanding_principal, 'rate': loan.interest_rate,
                    'accrued': loan.outstanding_interest, 'account_type': 'Loan',
                    'category': 'loan', 'obj': loan,
                    'last_calc_date': loan.last_interest_calculated_date,
                    'last_post_date': None,
                })

        return rows

    def get(self, request):
        branch = getattr(request, 'current_branch', None)
        if not branch:
            messages.error(request, 'Please select a branch first.')
            return redirect('dashboard:index')

        account_type = request.GET.get('account_type', 'all')
        rows = self._get_accounts(request, branch, account_type)
        total_balance = sum(r['balance'] for r in rows)
        total_accrued = sum(r['accrued'] for r in rows)
        already_calculated_today = sum(
            1 for r in rows if r['last_calc_date'] == date.today()
        )
        summary = {
            'total_accounts': len(rows), 'total_balance': total_balance,
            'total_accrued': total_accrued, 'already_calculated_today': already_calculated_today,
        }

        return render(request, 'dayend/interest_calculate.html', {
            'accounts': rows[:200], 'summary': summary, 'calc_date': date.today(),
            'account_type': account_type,
        })

    def post(self, request):
        branch = getattr(request, 'current_branch', None)
        if not branch:
            messages.error(request, 'Please select a branch.')
            return redirect('dayend:interest_calculate')

        calc_date_str = request.POST.get('calc_date', '')
        try:
            calc_date = date.fromisoformat(calc_date_str)
        except (ValueError, TypeError):
            calc_date = date.today()

        account_type = request.POST.get('account_type', 'all')
        rows = self._get_accounts(request, branch, account_type)

        calculated_count = 0
        skipped_count = 0
        total_interest = Decimal('0')
        results = []

        with transaction.atomic():
            for row in rows:
                obj = row['obj']

                if row['last_calc_date'] == calc_date:
                    skipped_count += 1
                    continue

                daily_interest = (row['balance'] * row['rate'] / 100 / 365).quantize(Decimal('0.01'))
                if daily_interest <= 0:
                    continue

                if row['category'] == 'savings':
                    obj.accrued_interest = F('accrued_interest') + daily_interest
                    obj.last_interest_calculated_date = calc_date
                    obj.save(update_fields=['accrued_interest', 'last_interest_calculated_date'])
                elif row['category'] == 'fd':
                    obj.accrued_interest = F('accrued_interest') + daily_interest
                    obj.last_interest_calculated_date = calc_date
                    obj.save(update_fields=['accrued_interest', 'last_interest_calculated_date'])
                elif row['category'] == 'loan':
                    obj.outstanding_interest = F('outstanding_interest') + daily_interest
                    obj.last_interest_calculated_date = calc_date
                    obj.save(update_fields=['outstanding_interest', 'last_interest_calculated_date'])
                else:
                    continue

                calculated_count += 1
                total_interest += daily_interest
                results.append({
                    'account_no': row['account_no'], 'member_name': row['member_name'],
                    'member_id': row['member_id'],
                    'balance': row['balance'], 'rate': row['rate'],
                    'daily_interest': daily_interest, 'account_type': row['account_type'],
                })

        if skipped_count > 0:
            messages.warning(
                request,
                f'{skipped_count} account(s) skipped — already calculated for {calc_date:%d %b %Y}.',
            )

        if calculated_count > 0:
            messages.success(
                request,
                f'Interest calculated for {calculated_count} accounts. Total: ₹{total_interest:,.2f}',
            )
        elif skipped_count == 0:
            messages.info(request, 'No eligible accounts found for interest calculation.')

        rows_refreshed = self._get_accounts(request, branch, account_type)
        total_balance = sum(r['balance'] for r in rows_refreshed)
        total_accrued = sum(r['accrued'] for r in rows_refreshed)
        already_calculated_today = sum(
            1 for r in rows_refreshed if r['last_calc_date'] == calc_date
        )
        summary = {
            'total_accounts': len(rows_refreshed), 'total_balance': total_balance,
            'total_accrued': total_accrued, 'already_calculated_today': already_calculated_today,
        }

        return render(request, 'dayend/interest_calculate.html', {
            'accounts': rows_refreshed[:200], 'summary': summary, 'calc_date': calc_date,
            'results': results, 'calculated_count': calculated_count,
            'skipped_count': skipped_count, 'total_interest': total_interest,
            'account_type': account_type,
        })


class InterestPostView(ManagerRequiredMixin, View):
    def _get_postable(self, request, branch, lock=False):
        from apps.deposits.models import FixedDeposit
        from apps.savings.models import SavingsAccount

        branch_filter = {} if request.user.can_access_all_branches else {'branch': branch}
        rows = []

        sb_qs = SavingsAccount.objects.filter(
            status='active', accrued_interest__gt=0, **branch_filter,
        ).select_related('member', 'branch')
        if lock:
            sb_qs = sb_qs.select_for_update()
        for a in sb_qs:
            rows.append({
                'account_no': a.account_no, 'member_name': a.member.name,
                'balance': a.current_balance, 'accrued': a.accrued_interest,
                'after_post': a.current_balance + a.accrued_interest,
                'account_type': f'SB-{a.get_account_type_display()}',
                'category': 'savings', 'obj': a,
                'last_post_date': a.last_interest_posted_date,
            })

        fd_qs = FixedDeposit.objects.filter(
            status='active', accrued_interest__gt=0, **branch_filter,
        ).select_related('member', 'branch')
        if lock:
            fd_qs = fd_qs.select_for_update()
        for fd in fd_qs:
            rows.append({
                'account_no': fd.fd_no, 'member_name': fd.member.name,
                'balance': fd.deposit_amount, 'accrued': fd.accrued_interest,
                'after_post': fd.deposit_amount + fd.accrued_interest,
                'account_type': 'Fixed Deposit',
                'category': 'fd', 'obj': fd,
                'last_post_date': fd.last_interest_posted_date,
            })

        return rows

    def _get_recent_postings(self, request, branch):
        from apps.accounting.models import JournalEntry

        branch_filter = {} if request.user.can_access_all_branches else {'branch': branch}
        entries = (
            JournalEntry.objects.filter(
                reference_type='interest_posting', is_reversed=False, **branch_filter,
            )
            .prefetch_related('lines__gl_account')
            .order_by('-entry_date', '-created_at')[:50]
        )
        today = date.today()
        wd = WorkingDay.objects.filter(branch=branch).first()
        day_is_open = wd and wd.is_day_open and not wd.day_end_completed
        postings = []
        for e in entries:
            amount = sum(l.debit_amount for l in e.lines.all())
            postings.append({
                'id': e.pk, 'voucher_no': e.voucher_no, 'date': e.entry_date,
                'narration': e.narration, 'amount': amount,
                'can_rollback': day_is_open and e.entry_date == today,
            })
        return postings

    def get(self, request):
        branch = getattr(request, 'current_branch', None)
        if not branch:
            messages.error(request, 'Please select a branch first.')
            return redirect('dashboard:index')

        rows = self._get_postable(request, branch)
        total_accrued = sum(r['accrued'] for r in rows)
        summary = {'total_accounts': len(rows), 'total_accrued': total_accrued}

        recent = self._get_recent_postings(request, branch)
        total_posted_recently = sum(p['amount'] for p in recent)
        today_postings = [p for p in recent if p['can_rollback']]

        return render(request, 'dayend/interest_post.html', {
            'accounts': rows[:200], 'summary': summary, 'post_date': date.today(),
            'recent_postings': recent, 'total_posted_recently': total_posted_recently,
            'today_posting_count': len(today_postings),
            'today_posting_total': sum(p['amount'] for p in today_postings),
        })

    def post(self, request):
        branch = getattr(request, 'current_branch', None)
        if not branch:
            messages.error(request, 'Please select a branch.')
            return redirect('dayend:interest_post')

        post_date_str = request.POST.get('post_date', '')
        try:
            post_date = date.fromisoformat(post_date_str)
        except (ValueError, TypeError):
            post_date = date.today()

        from apps.accounting.services import create_journal_entry
        from apps.core.gl_utils import get_gl_code, get_interest_head_code
        from apps.savings.models import AccountTransaction

        posted_count = 0
        total_posted = Decimal('0')
        results = []

        with transaction.atomic():
            rows = self._get_postable(request, branch, lock=True)

            if not rows:
                messages.info(request, 'No accounts with accrued interest to post.')
                return redirect('dayend:interest_post')

            for row in rows:
                obj = row['obj']
                interest_amount = row['accrued']
                if interest_amount <= 0:
                    continue

                if row['category'] == 'savings':
                    obj.current_balance += interest_amount
                    obj.interest_charged += interest_amount
                    obj.accrued_interest = Decimal('0')
                    obj.last_interest_posted_date = post_date
                    obj.save(update_fields=[
                        'current_balance', 'interest_charged',
                        'accrued_interest', 'last_interest_posted_date',
                    ])

                    txn = AccountTransaction.objects.create(
                        account=obj, branch=obj.branch,
                        txn_date=post_date, value_date=post_date,
                        txn_type='interest_credit', amount=interest_amount,
                        running_balance=obj.current_balance,
                        narration=f'Interest credited for period ending {post_date}',
                        payment_mode='transfer', created_by=request.user,
                    )

                    from apps.core.gl_utils import get_account_gl_code
                    savings_code = get_account_gl_code(obj, 'saving', '2001')
                    gl_head = obj.gl_head if hasattr(obj, 'gl_head') and obj.gl_head_id else None
                    interest_expense_code = get_interest_head_code(gl_head, get_gl_code('interest_paid', '4001'))
                    create_journal_entry(
                        entry_date=post_date, voucher_type='journal', branch=obj.branch,
                        narration=f'Interest on savings {obj.account_no}',
                        lines=[
                            {'account_code': interest_expense_code, 'debit': interest_amount, 'credit': Decimal('0')},
                            {'account_code': savings_code, 'debit': Decimal('0'), 'credit': interest_amount},
                        ],
                        user=request.user, reference_type='interest_posting', reference_id=txn.pk,
                    )

                elif row['category'] == 'fd':
                    obj.accrued_interest = Decimal('0')
                    obj.last_interest_posted_date = post_date
                    obj.save(update_fields=['accrued_interest', 'last_interest_posted_date'])

                    fd_code = get_gl_code('fixed', '2002')
                    interest_expense_code = get_gl_code('interest_paid', '4002')
                    if hasattr(obj, 'gl_head') and obj.gl_head_id and obj.gl_head.interest_code_id:
                        interest_expense_code = obj.gl_head.interest_code.code
                    create_journal_entry(
                        entry_date=post_date, voucher_type='journal', branch=obj.branch,
                        narration=f'Interest on FD {obj.fd_no}',
                        lines=[
                            {'account_code': interest_expense_code, 'debit': interest_amount, 'credit': Decimal('0')},
                            {'account_code': fd_code, 'debit': Decimal('0'), 'credit': interest_amount},
                        ],
                        user=request.user, reference_type='interest_posting',
                    )

                posted_count += 1
                total_posted += interest_amount
                results.append({
                    'account_no': row['account_no'], 'member_name': row['member_name'],
                    'balance': row['balance'], 'accrued': interest_amount,
                    'after_post': row['after_post'], 'account_type': row['account_type'],
                })

        if posted_count > 0:
            from apps.audit.services import log_action

            log_action(
                user=request.user, branch=branch, action='approve',
                table_name='InterestPosting', record_id=0,
                new_values={'posted_count': posted_count, 'total': str(total_posted), 'post_date': str(post_date)},
                ip_address=request.META.get('REMOTE_ADDR'),
            )

        remaining = self._get_postable(request, branch)
        total_remaining = sum(r['accrued'] for r in remaining)
        summary = {'total_accounts': len(remaining), 'total_accrued': total_remaining}

        return render(request, 'dayend/interest_post.html', {
            'accounts': remaining[:200], 'summary': summary, 'post_date': post_date,
            'results': results, 'posted_count': posted_count, 'total_posted': total_posted,
        })


@manager_required
@day_open_required
def rollback_interest_posting(request, entry_id):
    if request.method != 'POST':
        return redirect('dayend:interest_post')

    from apps.accounting.models import JournalEntry
    from apps.accounting.services import reverse_journal_entry
    from apps.savings.models import AccountTransaction

    entry = get_object_or_404(
        JournalEntry, pk=entry_id,
        reference_type='interest_posting', is_reversed=False,
    )
    if entry.entry_date != date.today():
        messages.error(request, 'Rollback is only allowed for same-day postings.')
        return redirect('dayend:interest_post')

    interest_amount = sum(l.debit_amount for l in entry.lines.all())

    with transaction.atomic():
        if entry.reference_id:
            txn = AccountTransaction.objects.filter(pk=entry.reference_id).select_related('account').first()
            if txn:
                acct = txn.account
                acct.current_balance -= interest_amount
                acct.interest_charged -= interest_amount
                acct.accrued_interest = interest_amount
                acct.last_interest_posted_date = None
                acct.save(update_fields=[
                    'current_balance', 'interest_charged',
                    'accrued_interest', 'last_interest_posted_date',
                ])
                txn.delete()
        else:
            from apps.deposits.models import FixedDeposit

            narration = entry.narration
            if 'FD ' in narration:
                fd_no = narration.split('FD ')[-1].strip()
                fd = FixedDeposit.objects.filter(fd_no=fd_no).first()
                if fd:
                    fd.accrued_interest = interest_amount
                    fd.last_interest_posted_date = None
                    fd.save(update_fields=['accrued_interest', 'last_interest_posted_date'])

        reverse_journal_entry(entry, request.user)

    messages.success(request, f'Interest posting reversed: {entry.voucher_no} (₹{interest_amount})')
    return redirect('dayend:interest_post')


@manager_required
@day_open_required
def rollback_all_interest_postings(request):
    if request.method != 'POST':
        return redirect('dayend:interest_post')

    from apps.accounting.models import JournalEntry
    from apps.accounting.services import reverse_journal_entry
    from apps.savings.models import AccountTransaction

    today = date.today()
    entries = JournalEntry.objects.filter(
        reference_type='interest_posting', is_reversed=False, entry_date=today,
    ).prefetch_related('lines__gl_account')

    if not entries.exists():
        messages.info(request, 'No interest postings to rollback for today.')
        return redirect('dayend:interest_post')

    rolled_back = 0
    total_amount = Decimal('0')

    with transaction.atomic():
        for entry in entries:
            interest_amount = sum(l.debit_amount for l in entry.lines.all())

            if entry.reference_id:
                txn = AccountTransaction.objects.filter(pk=entry.reference_id).select_related('account').first()
                if txn:
                    acct = txn.account
                    acct.current_balance -= interest_amount
                    acct.interest_charged -= interest_amount
                    acct.accrued_interest = interest_amount
                    acct.last_interest_posted_date = None
                    acct.save(update_fields=[
                        'current_balance', 'interest_charged',
                        'accrued_interest', 'last_interest_posted_date',
                    ])
                    txn.delete()
            else:
                from apps.deposits.models import FixedDeposit

                narration = entry.narration
                if 'FD ' in narration:
                    fd_no = narration.split('FD ')[-1].strip()
                    fd = FixedDeposit.objects.filter(fd_no=fd_no).first()
                    if fd:
                        fd.accrued_interest = interest_amount
                        fd.last_interest_posted_date = None
                        fd.save(update_fields=['accrued_interest', 'last_interest_posted_date'])

            reverse_journal_entry(entry, request.user)
            rolled_back += 1
            total_amount += interest_amount

    messages.success(request, f'Rolled back {rolled_back} interest posting(s) — total ₹{total_amount}')
    return redirect('dayend:interest_post')
