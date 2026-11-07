from django.contrib import admin

from .models import EmailLog, NotificationTemplate, SMSLog


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'channel', 'is_active', 'updated_at']
    list_filter = ['channel', 'is_active']
    search_fields = ['name']


@admin.register(SMSLog)
class SMSLogAdmin(admin.ModelAdmin):
    list_display = ['phone_number', 'message_type', 'status', 'sent_at']
    list_filter = ['status', 'message_type']
    search_fields = ['phone_number']
    readonly_fields = [
        'member',
        'phone_number',
        'message_type',
        'message_text',
        'sent_at',
        'status',
        'provider_message_id',
        'error_message',
    ]


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ['email_address', 'subject', 'status', 'sent_at']
    list_filter = ['status']
    search_fields = ['email_address', 'subject']
    readonly_fields = ['member', 'email_address', 'subject', 'body', 'sent_at', 'status', 'error_message']
