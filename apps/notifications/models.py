from django.db import models


class NotificationTemplate(models.Model):
    CHANNEL_CHOICES = [
        ('sms', 'SMS'),
        ('email', 'Email'),
        ('whatsapp', 'WhatsApp'),
    ]
    name = models.CharField(max_length=100, unique=True)
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES)
    subject = models.CharField(max_length=200, blank=True, help_text='Subject line for email notifications')
    template_text = models.TextField(help_text='Use {{member_name}}, {{amount}}, {{balance}} etc.')
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.name} ({self.get_channel_display()})'


class SMSLog(models.Model):
    member = models.ForeignKey('members.Member', on_delete=models.SET_NULL, null=True)
    phone_number = models.CharField(max_length=15)
    message_type = models.CharField(max_length=30)
    message_text = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=10,
        choices=[
            ('queued', 'Queued'),
            ('sent', 'Sent'),
            ('failed', 'Failed'),
            ('delivered', 'Delivered'),
        ],
        default='queued',
    )
    provider_message_id = models.CharField(max_length=100, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ['-sent_at']

    def __str__(self):
        return f'{self.phone_number} - {self.message_type} - {self.status}'


class EmailLog(models.Model):
    member = models.ForeignKey('members.Member', on_delete=models.SET_NULL, null=True, blank=True)
    email_address = models.EmailField()
    subject = models.CharField(max_length=200)
    body = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=10,
        choices=[
            ('queued', 'Queued'),
            ('sent', 'Sent'),
            ('failed', 'Failed'),
        ],
        default='queued',
    )
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ['-sent_at']

    def __str__(self):
        return f'{self.email_address} - {self.subject[:30]} - {self.status}'
