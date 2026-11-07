from django.conf import settings
from django.db import models


class FDProduct(models.Model):
    name = models.CharField(max_length=100)
    min_amount = models.DecimalField(max_digits=15, decimal_places=2)
    max_amount = models.DecimalField(max_digits=15, decimal_places=2)
    min_tenure_days = models.IntegerField()
    max_tenure_days = models.IntegerField()
    interest_rates = models.JSONField(default=list, help_text='[{min_days, max_days, rate, senior_rate}]')
    compounding = models.CharField(
        max_length=20,
        choices=[
            ('quarterly', 'Quarterly'),
            ('half_yearly', 'Half Yearly'),
            ('yearly', 'Yearly'),
            ('cumulative', 'Cumulative'),
        ],
        default='quarterly',
    )
    premature_penalty_percent = models.DecimalField(max_digits=5, decimal_places=2, default=1)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    def get_rate_for_tenure(self, tenure_days, is_senior=False):
        for slab in self.interest_rates:
            min_d = slab.get('min_days', 0)
            max_d = slab.get('max_days', 99999)
            if min_d <= tenure_days <= max_d:
                return slab.get('senior_rate' if is_senior else 'rate')
        return None


class FixedDeposit(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('matured', 'Matured'),
        ('prematurely_closed', 'Prematurely Closed'),
        ('renewed', 'Renewed'),
    ]
    member = models.ForeignKey('members.Member', on_delete=models.PROTECT, related_name='fixed_deposits')
    branch = models.ForeignKey('branches.Branch', on_delete=models.PROTECT)
    fd_product = models.ForeignKey(FDProduct, on_delete=models.PROTECT)
    fd_no = models.CharField(max_length=20, unique=True)
    deposit_amount = models.DecimalField(max_digits=15, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    senior_citizen_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    start_date = models.DateField()
    maturity_date = models.DateField()
    tenure_days = models.IntegerField()
    maturity_amount = models.DecimalField(max_digits=15, decimal_places=2)
    accrued_interest = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    is_auto_renew = models.BooleanField(default=False)
    compounding_type = models.CharField(max_length=20, default='quarterly')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    premature_closure_date = models.DateField(null=True, blank=True)
    premature_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    linked_savings_account = models.ForeignKey(
        'savings.SavingsAccount', on_delete=models.SET_NULL, null=True, blank=True
    )
    transfer_to_account = models.ForeignKey(
        'savings.SavingsAccount',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fd_transfer_target',
        help_text='Savings account for maturity credit',
    )
    tds_applicable = models.BooleanField(default=False)
    tds_deducted = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    certificate_no = models.CharField(max_length=50, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f'{self.fd_no} - {self.member.name} - {self.deposit_amount}'


class RecurringDeposit(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('matured', 'Matured'),
        ('defaulted', 'Defaulted'),
        ('closed', 'Closed'),
    ]
    member = models.ForeignKey('members.Member', on_delete=models.PROTECT, related_name='recurring_deposits')
    branch = models.ForeignKey('branches.Branch', on_delete=models.PROTECT)
    rd_no = models.CharField(max_length=20, unique=True)
    monthly_installment = models.DecimalField(max_digits=15, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    start_date = models.DateField()
    maturity_date = models.DateField()
    tenure_months = models.IntegerField()
    maturity_amount = models.DecimalField(max_digits=15, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    default_count = models.IntegerField(default=0)
    max_defaults_allowed = models.IntegerField(default=3)
    linked_savings_account = models.ForeignKey(
        'savings.SavingsAccount', on_delete=models.SET_NULL, null=True, blank=True
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f'{self.rd_no} - {self.member.name} - {self.monthly_installment}/mo'


class RDInstallment(models.Model):
    rd = models.ForeignKey(RecurringDeposit, on_delete=models.CASCADE, related_name='installments')
    installment_no = models.IntegerField()
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    paid_date = models.DateField(null=True, blank=True)
    penalty = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    status = models.CharField(
        max_length=10,
        choices=[
            ('pending', 'Pending'),
            ('paid', 'Paid'),
            ('overdue', 'Overdue'),
            ('defaulted', 'Defaulted'),
        ],
        default='pending',
    )
    branch = models.ForeignKey('branches.Branch', on_delete=models.PROTECT, null=True, blank=True)

    class Meta:
        ordering = ['due_date']
        unique_together = ['rd', 'installment_no']

    def __str__(self):
        return f'{self.rd.rd_no} - Inst #{self.installment_no}'
