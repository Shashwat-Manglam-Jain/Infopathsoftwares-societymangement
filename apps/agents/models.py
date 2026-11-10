from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Agent(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('terminated', 'Terminated'),
    ]

    agent_code = models.CharField(max_length=10, unique=True)
    member = models.OneToOneField(
        'members.Member',
        on_delete=models.PROTECT,
        related_name='agent_profile',
        help_text='Agent must be a registered member',
    )
    branch = models.ForeignKey('branches.Branch', on_delete=models.PROTECT, related_name='agents')
    savings_account = models.ForeignKey(
        'savings.SavingsAccount',
        on_delete=models.PROTECT,
        related_name='agent_savings',
        help_text='Agent must have a savings account for commission credit',
    )
    security_deposit_account = models.ForeignKey(
        'savings.SavingsAccount',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='agent_security',
        help_text='Agent security deposit account',
    )
    security_deposit_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    loan_account_number = models.CharField(max_length=20, blank=True)
    security_document = models.FileField(upload_to='agents/documents/', blank=True)
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('2.00'),
        help_text='Commission percentage on collections',
    )
    joining_date = models.DateField()
    phone = models.CharField(max_length=15)
    area = models.CharField(max_length=200, blank=True, help_text='Collection area/route')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='active')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['agent_code']

    def __str__(self):
        return f'{self.agent_code} - {self.member.name}'


class PigmmyAccount(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('matured', 'Matured'),
        ('closed', 'Closed'),
        ('defaulted', 'Defaulted'),
    ]
    DEPOSIT_TYPE_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]

    CLIENT_TYPE_CHOICES = [
        ('D', 'Daily'),
        ('M', 'Monthly'),
        ('L', 'Loan'),
    ]

    account_no = models.CharField(max_length=20, unique=True)
    ledger_number = models.PositiveBigIntegerField(null=True, blank=True)
    folio_number = models.CharField(max_length=10, blank=True)
    member = models.ForeignKey(
        'members.Member',
        on_delete=models.PROTECT,
        related_name='pigmmy_accounts',
    )
    branch = models.ForeignKey('branches.Branch', on_delete=models.PROTECT)
    agent = models.ForeignKey(Agent, on_delete=models.PROTECT, related_name='client_accounts')
    linked_savings_account = models.ForeignKey(
        'savings.SavingsAccount',
        on_delete=models.PROTECT,
        related_name='pigmmy_accounts',
        null=True,
        blank=True,
        help_text='Savings account for maturity credit',
    )
    security_deposit_account = models.ForeignKey(
        'savings.SavingsAccount',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pigmmy_sd_accounts',
        help_text='Security deposit account',
    )
    loan_account_number = models.CharField(max_length=20, blank=True)
    client_type = models.CharField(
        max_length=1,
        choices=CLIENT_TYPE_CHOICES,
        default='D',
        help_text='Type: D=Daily, M=Monthly, L=Loan',
    )
    deposit_type = models.CharField(
        max_length=10,
        choices=DEPOSIT_TYPE_CHOICES,
        default='daily',
    )
    installment_amount = models.DecimalField(max_digits=15, decimal_places=2)
    deposit_period_months = models.IntegerField(help_text='Total deposit period in months')
    deposit_units = models.CharField(max_length=10, blank=True, help_text='Period unit: days/months/years')
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    opening_date = models.DateField()
    expiry_date = models.DateField(null=True, blank=True, help_text='Expected expiry/maturity date')
    maturity_date = models.DateField()
    maturity_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    current_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    total_deposited = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    total_installments = models.IntegerField(default=0)
    paid_installments = models.IntegerField(default=0)
    missed_installments = models.IntegerField(default=0)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='active')
    meeting_no = models.CharField(max_length=20, blank=True, help_text='Board Meeting Number')
    meeting_date = models.DateField(null=True, blank=True, help_text='Board Meeting Date')
    sign = models.IntegerField(default=0, help_text='1=debit nature, -1=credit nature, 0=default')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['account_no']

    def __str__(self):
        return f'{self.account_no} - {self.member.name}'

    def clean(self):
        if self.client_type == 'D' and self.status == 'active':
            qs = PigmmyAccount.objects.filter(
                member=self.member,
                client_type='D',
                status='active',
            )
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError('Member already has an active daily pigmmy account.')


class PigmmyTransaction(models.Model):
    account = models.ForeignKey(
        PigmmyAccount,
        on_delete=models.PROTECT,
        related_name='transactions',
    )
    branch = models.ForeignKey('branches.Branch', on_delete=models.PROTECT)
    txn_date = models.DateField()
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    running_balance = models.DecimalField(max_digits=15, decimal_places=2)
    installment_no = models.IntegerField(null=True, blank=True)
    narration = models.CharField(max_length=300, blank=True)
    collected_by = models.ForeignKey(Agent, on_delete=models.PROTECT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    is_reversed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-txn_date', '-created_at']

    def __str__(self):
        return f'{self.account.account_no} - {self.amount} on {self.txn_date}'


class AgentCollection(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('submitted', 'Submitted'),
        ('reconciled', 'Reconciled'),
        ('discrepancy', 'Discrepancy'),
    ]

    agent = models.ForeignKey(Agent, on_delete=models.PROTECT, related_name='collections')
    branch = models.ForeignKey('branches.Branch', on_delete=models.PROTECT)
    collection_date = models.DateField()
    total_clients_visited = models.IntegerField(default=0)
    total_clients_collected = models.IntegerField(default=0)
    expected_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    collected_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    deposited_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    commission_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='open')
    reconciled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-collection_date']
        unique_together = ['agent', 'collection_date']

    def __str__(self):
        return f'{self.agent.agent_code} - {self.collection_date}'


class AgentCommission(models.Model):
    agent = models.ForeignKey(Agent, on_delete=models.PROTECT, related_name='commissions')
    month = models.DateField(help_text='First day of the commission month')
    total_collection = models.DecimalField(max_digits=15, decimal_places=2)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2)
    commission_amount = models.DecimalField(max_digits=15, decimal_places=2)
    tds_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    net_amount = models.DecimalField(max_digits=15, decimal_places=2)
    paid = models.BooleanField(default=False)
    paid_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['agent', 'month']

    def __str__(self):
        return f'{self.agent.agent_code} - {self.month}'
