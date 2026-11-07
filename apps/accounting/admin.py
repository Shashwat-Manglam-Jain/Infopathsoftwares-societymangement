from django.contrib import admin

from apps.accounting.models import ChartOfAccounts, JournalEntry, JournalLine


@admin.register(ChartOfAccounts)
class ChartOfAccountsAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'account_group', 'account_type', 'current_balance', 'is_system']
    list_filter = ['account_group', 'is_system', 'is_active']
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
