from django.contrib import admin

from apps.savings.models import AccountTransaction, SavingsAccount


@admin.register(SavingsAccount)
class SavingsAccountAdmin(admin.ModelAdmin):
    list_display = ['account_no', 'member', 'branch', 'account_type', 'current_balance', 'status']
    list_filter = ['status', 'account_type', 'branch']
    search_fields = ['account_no', 'member__name']
    readonly_fields = ['account_no', 'current_balance', 'created_at']


@admin.register(AccountTransaction)
class AccountTransactionAdmin(admin.ModelAdmin):
    list_display = ['account', 'txn_date', 'txn_type', 'amount', 'running_balance', 'payment_mode']
    list_filter = ['txn_type', 'payment_mode', 'branch']
    date_hierarchy = 'txn_date'
    readonly_fields = ['running_balance', 'created_at']
