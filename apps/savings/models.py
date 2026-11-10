from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class SavingsAccount(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('dormant', 'Dormant'),
        ('closed', 'Closed'),
        ('frozen', 'Frozen'),
    ]
    member = models.ForeignKey('members.Member', on_delete=models.PROTECT, related_name='savings_accounts')
    branch = models.ForeignKey('branches.Branch', on_delete=models.PROTECT)
    account_no = models.CharField(max_length=20, unique=True, blank=True)
    ACCOUNT_TYPE_CHOICES = [
        ('savings', 'Savings Account'),
        ('current', 'Current Account'),
        ('security', 'Security Deposit'),
    ]
    account_type = models.CharField(max_length=10, choices=ACCOUNT_TYPE_CHOICES, default='savings')
    gl_head = models.ForeignKey(
        'accounting.ChartOfAccounts',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='savings_accounts',
        help_text='GL head this account belongs to',
    )
    ledger_number = models.PositiveBigIntegerField(null=True, blank=True)
    folio_number = models.CharField(max_length=10, blank=True)
    opening_date = models.DateField()
    closing_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    current_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    overdue_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    interest_charged = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    interest_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    penal_interest = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    accrued_interest = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    last_interest_calculated_date = models.DateField(null=True, blank=True)
    last_interest_posted_date = models.DateField(null=True, blank=True)
    minimum_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    introducer = models.ForeignKey(
        'members.Member',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='introduced_savings',
        help_text='Existing member who introduced this account',
    )
    sign = models.IntegerField(default=0, help_text='1=debit nature, -1=credit nature, 0=default')
    meeting_no = models.CharField(max_length=20, blank=True, help_text='Board Meeting Number')
    meeting_date = models.DateField(null=True, blank=True, help_text='Board Meeting Date')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='savings_accounts_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['account_no']

    def __str__(self):
        return f'{self.account_no} - {self.member.name}'

    def clean(self):
        if self.account_type == 'savings' and self.status == 'active':
            qs = SavingsAccount.objects.filter(
                member=self.member,
                account_type='savings',
                status='active',
            )
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError('Member already has an active savings account.')

    def save(self, *args, **kwargs):
        if not self.account_no:
            from apps.core.account_utils import generate_account_number

            type_codes = {'savings': '001', 'current': '002', 'security': '003'}
            code = type_codes.get(self.account_type, '001')
            self.account_no = generate_account_number(self.branch, code)
        super().save(*args, **kwargs)


class AccountTransaction(models.Model):
    TXN_TYPE_CHOICES = [
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('interest_credit', 'Interest Credit'),
        ('charge', 'Charge'),
        ('reversal', 'Reversal'),
        ('transfer', 'Transfer'),
    ]
    PAYMENT_MODE_CHOICES = [
        ('cash', 'Cash'),
        ('cheque', 'Cheque'),
        ('transfer', 'Transfer'),
        ('upi', 'UPI'),
    ]

    account = models.ForeignKey(SavingsAccount, on_delete=models.PROTECT, related_name='transactions')
    branch = models.ForeignKey('branches.Branch', on_delete=models.PROTECT)
    txn_date = models.DateField()
    value_date = models.DateField()
    txn_type = models.CharField(max_length=20, choices=TXN_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    running_balance = models.DecimalField(max_digits=15, decimal_places=2)
    narration = models.CharField(max_length=300, blank=True)
    voucher_no = models.CharField(max_length=30, blank=True)
    receipt_no = models.CharField(max_length=30, blank=True)
    payment_mode = models.CharField(max_length=10, choices=PAYMENT_MODE_CHOICES, default='cash')
    cheque_no = models.CharField(max_length=20, blank=True)
    cheque_date = models.DateField(null=True, blank=True)
    bank_name = models.CharField(max_length=100, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='savings_txns')
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_savings_txns'
    )
    is_reversed = models.BooleanField(default=False)
    reversal_of = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-txn_date', '-created_at']

    def __str__(self):
        return f'{self.account.account_no} - {self.get_txn_type_display()} - {self.amount}'
