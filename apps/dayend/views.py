from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.views import View

from .models import DayEndLog, FinancialYear, MonthEndLog, WorkingDay, YearEndLog


@login_required
def dayend_index(request):
    branch = getattr(request, 'current_branch', None)
    if not branch:
        messages.error(request, 'Please select a branch first.')
        return redirect('dashboard:index')

    working_day = WorkingDay.objects.filter(branch=branch).first()
    logs = DayEndLog.objects.filter(branch=branch)[:30]
    month_logs = MonthEndLog.objects.filter(branch=branch)[:12]
    year_logs = YearEndLog.objects.filter(branch=branch)[:5]

    return render(
        request,
        'dayend/day_end.html',
        {
            'working_day': working_day,
            'logs': logs,
            'month_logs': month_logs,
            'year_logs': year_logs,
        },
    )


class BeginDayView(LoginRequiredMixin, View):
    def post(self, request):
        branch = getattr(request, 'current_branch', None)
        if not branch:
            messages.error(request, 'Please select a branch.')
            return redirect('dayend:index')

        working_date_str = request.POST.get('working_date')
        if not working_date_str:
            working_date = date.today()
        else:
            from datetime import datetime

            try:
                working_date = datetime.strptime(working_date_str, '%Y-%m-%d').date()
            except ValueError:
                messages.error(request, 'Invalid date format.')
                return redirect('dayend:index')

        from .services import begin_working_day

        try:
            wd = begin_working_day(branch, working_date, request.user)
            messages.success(request, f'Working day opened: {wd.current_date}')
        except ValueError as e:
            messages.error(request, str(e))

        return redirect('dayend:index')


class RunDayEndView(LoginRequiredMixin, View):
    def post(self, request):
        branch = getattr(request, 'current_branch', None)
        if not branch:
            messages.error(request, 'Please select a branch.')
            return redirect('dayend:index')

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
        except ValueError as e:
            messages.error(request, str(e))

        return redirect('dayend:index')


class RollbackDayEndView(LoginRequiredMixin, View):
    def post(self, request):
        branch = getattr(request, 'current_branch', None)
        if not branch:
            messages.error(request, 'Please select a branch.')
            return redirect('dayend:index')

        processing_date_str = request.POST.get('processing_date')
        if not processing_date_str:
            messages.error(request, 'Processing date is required.')
            return redirect('dayend:index')

        from datetime import datetime

        try:
            processing_date = datetime.strptime(processing_date_str, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, 'Invalid date format.')
            return redirect('dayend:index')

        from .services import rollback_day_end

        try:
            rollback_day_end(branch, processing_date, request.user)
            messages.success(request, f'Day End rolled back for {processing_date}. Day is now open.')
        except ValueError as e:
            messages.error(request, str(e))

        return redirect('dayend:index')


class RunMonthEndView(LoginRequiredMixin, View):
    def post(self, request):
        branch = getattr(request, 'current_branch', None)
        if not branch:
            messages.error(request, 'Please select a branch.')
            return redirect('dayend:index')

        month_str = request.POST.get('month')
        if not month_str:
            month_date = date.today().replace(day=1)
        else:
            from datetime import datetime

            try:
                month_date = datetime.strptime(month_str + '-01', '%Y-%m-%d').date()
            except ValueError:
                messages.error(request, 'Invalid month format. Use YYYY-MM.')
                return redirect('dayend:index')

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


class RunYearEndView(LoginRequiredMixin, View):
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
