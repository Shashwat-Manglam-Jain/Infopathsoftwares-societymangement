from django.contrib import admin

from apps.accounting.models import CashbookMaster, ChartOfAccounts, InterestMaster, JournalEntry, JournalLine


@admin.register(ChartOfAccounts)
class ChartOfAccountsAdmin(admin.ModelAdmin):
    list_display = [
        'code',
        'name',
        'account_group',
        'related_table_name',
        'opening_balance',
        'credit_balance',
        'debit_balance',
        'current_balance',
        'is_system',
    ]
    list_filter = ['account_group', 'related_table_name', 'is_system', 'is_active']
    search_fields = ['code', 'name']


class JournalLineInline(admin.TabularInline):
    model = JournalLine
    extra = 0


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ['voucher_no', 'entry_date', 'voucher_type', 'branch', 'narration', 'is_reversed']
    list_filter = ['voucher_type', 'branch', 'is_reversed']
    date_hierarchy = 'entry_date'
    inlines = [JournalLineInline]


@admin.register(InterestMaster)
class InterestMasterAdmin(admin.ModelAdmin):
    list_display = [
        'account_head',
        'min_period',
        'max_period',
        'period_unit',
        'interest_rate',
        'penal_rate',
        'is_active',
    ]
    list_filter = ['period_unit', 'is_active', 'account_head']


@admin.register(CashbookMaster)
class CashbookMasterAdmin(admin.ModelAdmin):
    list_display = [
        'branch',
        'txn_date',
        'opening_balance',
        'total_receipts',
        'total_payments',
        'closing_balance',
        'is_closed',
    ]
    list_filter = ['branch', 'is_closed']
    date_hierarchy = 'txn_date'
