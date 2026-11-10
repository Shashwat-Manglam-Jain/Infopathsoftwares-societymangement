from django.contrib import admin
from django_tenants.admin import TenantAdminMixin

from .models import Domain, Society, Subscription, SubscriptionPlan

admin.site.site_header = 'InfoSociety Administration'
admin.site.site_title = 'InfoSociety Admin'
admin.site.index_title = 'Society Management & Monitoring'


class DomainInline(admin.TabularInline):
    model = Domain
    extra = 0


class SubscriptionInline(admin.StackedInline):
    model = Subscription
    extra = 0
    readonly_fields = ('is_expired', 'days_remaining')


@admin.register(Society)
class SocietyAdmin(TenantAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'schema_name', 'society_type', 'registration_no', 'city', 'is_active', 'created_at')
    list_filter = ('society_type', 'is_active', 'city', 'state')
    search_fields = ('name', 'registration_no', 'city', 'email')
    readonly_fields = ('schema_name', 'created_at')
    inlines = [DomainInline, SubscriptionInline]
    fieldsets = (
        (None, {'fields': ('name', 'schema_name', 'society_type', 'is_active')}),
        (
            'Registration',
            {'fields': ('registration_no', 'registration_date', 'registration_authority', 'society_category')},
        ),
        ('Contact', {'fields': ('address', 'city', 'state', 'pincode', 'phone', 'fax', 'email')}),
        ('Financial', {'fields': ('authorized_capital', 'paid_up_capital', 'share_nominal_value')}),
        ('Tax', {'fields': ('pan_no', 'tan_no', 'gst_no'), 'classes': ('collapse',)}),
        ('Other', {'fields': ('name_regional', 'logo', 'created_at'), 'classes': ('collapse',)}),
    )


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ('domain', 'tenant', 'is_primary')
    list_filter = ('is_primary',)
    search_fields = ('domain', 'tenant__name')


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'max_members', 'max_users', 'max_branches', 'price_monthly', 'is_active')
    list_filter = ('is_active',)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('society', 'plan', 'status', 'is_trial', 'start_date', 'end_date')
    list_filter = ('status', 'is_trial', 'plan')
    search_fields = ('society__name',)
    readonly_fields = ('is_expired', 'days_remaining')
