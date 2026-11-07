from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('super_admin', 'Super Admin'),
        ('branch_manager', 'Branch Manager'),
        ('cashier', 'Cashier'),
        ('accountant', 'Accountant'),
        ('auditor', 'Auditor'),
        ('member', 'Member'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='cashier')
    branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='staff',
    )
    phone = models.CharField(max_length=20, blank=True)
    profile_photo = models.ImageField(upload_to='staff/photos/', blank=True)
    can_access_all_branches = models.BooleanField(default=False)

    class Meta:
        db_table = 'auth_user'

    def __str__(self):
        return f'{self.get_full_name() or self.username} ({self.get_role_display()})'

    def get_short_name(self):
        return self.first_name or self.username

    @property
    def is_admin(self):
        return self.role == 'super_admin'

    @property
    def is_manager(self):
        return self.role in ('super_admin', 'branch_manager')

    @property
    def is_cashier(self):
        return self.role in ('super_admin', 'branch_manager', 'cashier')
