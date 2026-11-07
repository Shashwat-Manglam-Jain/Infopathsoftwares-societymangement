from django.contrib import admin

from apps.audit.models import AuditTrail


@admin.register(AuditTrail)
class AuditTrailAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'user', 'action', 'table_name', 'record_id', 'ip_address']
    list_filter = ['action', 'table_name']
    date_hierarchy = 'timestamp'
    readonly_fields = [
        'timestamp',
        'user',
        'branch',
        'action',
        'table_name',
        'record_id',
        'old_values',
        'new_values',
        'ip_address',
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
