from django.contrib import admin

from .models import Branch


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = [
        'branch_code',
        'branch_name',
        'city',
        'is_head_office',
        'status',
    ]
    list_filter = ['status', 'is_head_office', 'state']
    search_fields = ['branch_code', 'branch_name', 'city']
