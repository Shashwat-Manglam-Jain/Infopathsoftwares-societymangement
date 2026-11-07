from django.contrib import admin

from apps.dayend.models import DayEndLog, FinancialYear


@admin.register(DayEndLog)
class DayEndLogAdmin(admin.ModelAdmin):
    list_display = [
        'processing_date',
        'branch',
        'status',
        'savings_interest_accrued_count',
        'loan_interest_accrued_count',
        'loans_marked_overdue_count',
        'run_by',
    ]
    list_filter = ['status', 'branch']
    date_hierarchy = 'processing_date'


@admin.register(FinancialYear)
class FinancialYearAdmin(admin.ModelAdmin):
    list_display = ['fy_code', 'start_date', 'end_date', 'is_current', 'is_closed']
    list_filter = ['is_current', 'is_closed']
