from django.conf import settings
from django.db import models


class Branch(models.Model):
    branch_code = models.CharField(max_length=10, unique=True)
    branch_name = models.CharField(max_length=200)
    address = models.TextField(blank=True)
    address_line_2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=10, blank=True)
    country = models.CharField(max_length=50, default='India', blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    ifsc_code = models.CharField(max_length=11, blank=True)
    locker_facility = models.BooleanField(default=False)
    neft_imps_service = models.BooleanField(default=True)
    is_head_office = models.BooleanField(default=False)
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_branches',
    )
    opening_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=10,
        choices=[('active', 'Active'), ('inactive', 'Inactive')],
        default='active',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'branches'
        ordering = ['-is_head_office', 'branch_name']

    def __str__(self):
        suffix = ' (HO)' if self.is_head_office else ''
        return f'{self.branch_name}{suffix}'
