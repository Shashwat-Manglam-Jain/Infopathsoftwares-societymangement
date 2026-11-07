from django.contrib import admin

from apps.deposits.models import FDProduct, FixedDeposit, RDInstallment, RecurringDeposit


@admin.register(FDProduct)
class FDProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'min_amount', 'max_amount', 'compounding', 'is_active']


@admin.register(FixedDeposit)
class FixedDepositAdmin(admin.ModelAdmin):
    list_display = ['fd_no', 'member', 'deposit_amount', 'interest_rate', 'maturity_date', 'maturity_amount', 'status']
    list_filter = ['status', 'branch']
    search_fields = ['fd_no', 'member__name']


class RDInstallmentInline(admin.TabularInline):
    model = RDInstallment
    extra = 0


@admin.register(RecurringDeposit)
class RecurringDepositAdmin(admin.ModelAdmin):
    list_display = ['rd_no', 'member', 'monthly_installment', 'interest_rate', 'maturity_date', 'status']
    list_filter = ['status', 'branch']
    inlines = [RDInstallmentInline]
