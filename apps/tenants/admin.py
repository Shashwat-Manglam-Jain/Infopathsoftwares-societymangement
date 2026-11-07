from django.contrib import admin
from django_tenants.admin import TenantAdminMixin

from .models import Domain, Society, Subscription, SubscriptionPlan


@admin.register(Society)
class SocietyAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'society_type', 'city', 'is_active', 'created_at')
    list_filter = ('society_type', 'is_active')
    search_fields = ('name', 'registration_no', 'city')


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ('domain', 'tenant', 'is_primary')


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'max_members', 'max_branches', 'price_monthly', 'is_active')


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('society', 'plan', 'status', 'start_date', 'end_date')
    list_filter = ('status', 'is_trial')
