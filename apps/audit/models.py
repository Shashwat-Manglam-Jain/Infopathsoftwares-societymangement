from django.conf import settings
from django.db import models


class AuditTrail(models.Model):
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('reverse', 'Reverse'),
        ('approve', 'Approve'),
    ]
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    branch = models.ForeignKey('branches.Branch', on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    table_name = models.CharField(max_length=100)
    record_id = models.IntegerField()
    old_values = models.JSONField(null=True, blank=True)
    new_values = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['table_name', 'record_id']),
            models.Index(fields=['-timestamp']),
        ]

    def __str__(self):
        return f'{self.timestamp} - {self.user} - {self.action} {self.table_name}#{self.record_id}'
