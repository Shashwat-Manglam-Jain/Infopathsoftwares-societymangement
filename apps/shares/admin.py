from django.contrib import admin

from .models import ShareConfig, ShareHolding, ShareTransaction


@admin.register(ShareConfig)
class ShareConfigAdmin(admin.ModelAdmin):
    list_display = ['name', 'face_value_per_share', 'max_shares_per_member', 'is_active']


@admin.register(ShareHolding)
class ShareHoldingAdmin(admin.ModelAdmin):
    list_display = ['member', 'share_count', 'total_amount', 'certificate_no', 'status']
    list_filter = ['status', 'branch']
    search_fields = ['member__name', 'member__member_no', 'certificate_no']


@admin.register(ShareTransaction)
class ShareTransactionAdmin(admin.ModelAdmin):
    list_display = ['member', 'txn_type', 'shares_count', 'amount', 'txn_date']
    list_filter = ['txn_type', 'branch']
    search_fields = ['member__name', 'member__member_no']
