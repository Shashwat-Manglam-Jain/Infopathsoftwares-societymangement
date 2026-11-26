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
        ('director_security', 'Director Security Deposit'),
    ]
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES, default='savings', db_index=True)
    GL_RELATED_TYPES = ('saving', 'current', 'security')
    manual_account_no = models.CharField(max_length=20, blank=True, help_text='Legacy manual account number')
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
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active', db_index=True)
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
    INTEREST_POSTING_FREQUENCY_CHOICES = [
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ]
    interest_posting_frequency = models.CharField(
        max_length=10,
        choices=INTEREST_POSTING_FREQUENCY_CHOICES,
        default='yearly',
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

    def save(self, *args, **kwargs):
        if self.gl_head_id:
            related = self.gl_head.related_table_name
            type_map = {'saving': 'savings', 'current': 'current', 'security': 'security'}
            base_type = type_map.get(related, 'savings')
            if base_type == 'security' and 'director' in self.gl_head.name.lower():
                base_type = 'director_security'
            self.account_type = base_type
        if not self.account_no:
            from apps.core.account_utils import generate_account_number

            code = self._get_account_code()
            self.account_no = generate_account_number(self.branch, code)
        super().save(*args, **kwargs)

    def _get_account_code(self):
        if self.gl_head_id and self.gl_head.account_code:
            return self.gl_head.account_code

        from apps.accounting.models import ChartOfAccounts

        type_to_related = {
            'savings': 'saving',
            'current': 'current',
            'security': 'security',
            'director_security': 'security',
        }
        related = type_to_related.get(self.account_type, 'saving')

        qs = ChartOfAccounts.objects.filter(
            related_table_name=related,
            account_code__gt='',
            is_active=True,
        )
        if self.account_type == 'director_security':
            head = qs.filter(name__icontains='director').first() or qs.first()
        else:
            head = qs.exclude(name__icontains='director').first() or qs.first()
        if head and head.account_code:
            return head.account_code
        fallback = {
            'savings': '006',
            'current': '002',
            'security': '003',
            'director_security': '075',
        }
        return fallback.get(self.account_type, '006')

    def clean(self):
        if self.status == 'active' and (self.gl_head_id or self.account_type):
            if self.gl_head_id:
                qs = SavingsAccount.objects.filter(
                    member=self.member,
                    gl_head=self.gl_head,
                    status='active',
                )
            else:
                qs = SavingsAccount.objects.filter(
                    member=self.member,
                    account_type=self.account_type,
                    status='active',
                )
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                label = (
                    self.gl_head.name
                    if self.gl_head_id
                    else dict(self.ACCOUNT_TYPE_CHOICES).get(self.account_type, self.account_type)
                )
                raise ValidationError(f'Member already has an active {label}.')


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
    txn_date = models.DateField(db_index=True)
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
