from django.contrib import admin

from apps.loans.models import (
    EMISchedule,
    LoanAccount,
    LoanCollateral,
    LoanGuarantor,
    LoanProduct,
    LoanRepayment,
)


@admin.register(LoanProduct)
class LoanProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'interest_rate', 'max_amount', 'interest_type', 'is_active']
    list_filter = ['interest_type', 'is_active']


class GuarantorInline(admin.TabularInline):
    model = LoanGuarantor
    extra = 0


class CollateralInline(admin.TabularInline):
    model = LoanCollateral
    extra = 0


class EMIInline(admin.TabularInline):
    model = EMISchedule
    extra = 0
    readonly_fields = ['principal_component', 'interest_component', 'total_emi']


@admin.register(LoanAccount)
class LoanAccountAdmin(admin.ModelAdmin):
    list_display = ['loan_no', 'member', 'loan_product', 'disbursed_amount', 'outstanding_principal', 'status']
    list_filter = ['status', 'loan_product', 'branch']
    search_fields = ['loan_no', 'member__name']
    inlines = [GuarantorInline, CollateralInline, EMIInline]


@admin.register(LoanRepayment)
class LoanRepaymentAdmin(admin.ModelAdmin):
    list_display = ['loan', 'payment_date', 'amount', 'principal_adjusted', 'interest_adjusted', 'payment_mode']
    date_hierarchy = 'payment_date'
