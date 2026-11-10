from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
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
        return self.role == 'admin'

    @property
    def is_manager(self):
        return self.role in ('admin', 'branch_manager')

    @property
    def is_cashier(self):
        """Cashier or above — can do counter transactions."""
        return self.role in ('admin', 'branch_manager', 'cashier')

    @property
    def is_accountant(self):
        """Accountant or above — can do cashbook, vouchers, day-end."""
        return self.role in ('admin', 'branch_manager', 'accountant')

    @property
    def is_staff_role(self):
        """Any operational staff — cashier, accountant, manager, admin. NOT auditor/member."""
        return self.role in ('admin', 'branch_manager', 'cashier', 'accountant')

    @property
    def is_auditor_or_above(self):
        """Everyone except member — can view all data."""
        return self.role != 'member'

    @property
    def is_member_only(self):
        return self.role == 'member'
