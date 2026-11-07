from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'role', 'branch', 'is_active']
    list_filter = ['role', 'is_active', 'branch']
    fieldsets = UserAdmin.fieldsets + (
        (
            'Society Info',
            {
                'fields': ('phone', 'role', 'branch', 'can_access_all_branches'),
            },
        ),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            'Society Info',
            {
                'fields': ('phone', 'role', 'branch', 'can_access_all_branches'),
            },
        ),
    )
