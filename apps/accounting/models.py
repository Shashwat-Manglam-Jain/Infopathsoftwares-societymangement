from django.conf import settings
from django.db import models


class ChartOfAccounts(models.Model):
    ACCOUNT_GROUP_CHOICES = [
        ('asset', 'Asset'),
        ('liability', 'Liability'),
        ('income', 'Income'),
        ('expense', 'Expense'),
        ('equity', 'Equity'),
    ]

    RELATED_TABLE_CHOICES = [
        ('saving', 'Saving Account'),
        ('current', 'Current Account'),
        ('recurring', 'Recurring Deposit'),
        ('fixed', 'Fixed Deposit'),
        ('security', 'Security Deposit'),
        ('shares', 'Share Capital'),
        ('nominal', 'Nominal Account'),
        ('loan', 'Loan Account'),
        ('advance', 'Advance Account'),
        ('client', 'Client/Pigmmy Account'),
        ('agent', 'Agent Account'),
        ('general', 'General Account'),
        ('other', 'Other Account'),
        ('group', 'Group (Display Only)'),
        ('interest_received', 'Interest Received'),
        ('interest_receivable', 'Interest Receivable'),
        ('interest_paid', 'Interest Paid'),
        ('interest_payable', 'Interest Payable'),
        ('bank', 'Bank Investment'),
    ]

    REPORT_POSITION_CHOICES = [
        ('balance_sheet', 'Balance Sheet'),
        ('profit_loss', 'Profit & Loss'),
        ('trial_balance', 'Trial Balance Only'),
        ('none', 'None'),
    ]

    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=200)
    head_name_regional = models.CharField(max_length=200, blank=True, help_text='Name in regional language')
    account_group = models.CharField(max_length=10, choices=ACCOUNT_GROUP_CHOICES)
    account_type = models.CharField(max_length=50, blank=True)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children')
    account_code = models.CharField(
        max_length=3, blank=True, help_text='3-digit code used in account number generation'
    )
    is_system = models.BooleanField(default=False)
    branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text='NULL = society-wide, set = branch-specific (e.g. cash book)',
    )
    opening_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    credit_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    debit_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    current_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    sub_group = models.CharField(max_length=10, blank=True, help_text='Sub-group classification for reporting')
    is_active = models.BooleanField(default=True)

    related_table_name = models.CharField(
        max_length=25,
        choices=RELATED_TABLE_CHOICES,
        default='general',
        help_text='Determines which module handles accounts under this head',
    )
    interest_affected = models.BooleanField(
        default=False,
        help_text='Whether interest calculation affects this head balance',
    )
    overdue_affected = models.BooleanField(
        default=False,
        help_text='Whether overdue calculation affects this head balance',
    )
    interest_given = models.BooleanField(
        default=False,
        help_text='Whether interest is credited to accounts under this head',
    )
    interest_code = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='interest_linked_heads',
        help_text='Interest income/expense head for this account head',
    )
    report_position = models.CharField(
        max_length=15,
        choices=REPORT_POSITION_CHOICES,
        default='balance_sheet',
    )
    display_order = models.IntegerField(default=0)
    allow_transactions = models.BooleanField(
        default=True,
        help_text='Group/display-only heads do not allow transactions',
    )
    default_code = models.BooleanField(
        default=False,
        help_text='System-created head, cannot be deleted by users',
    )

    class Meta:
        verbose_name_plural = 'chart of accounts'
        ordering = ['display_order', 'code']

    def __str__(self):
        return f'{self.code} - {self.name}'


class JournalEntry(models.Model):
    VOUCHER_TYPE_CHOICES = [
        ('receipt', 'Receipt'),
        ('payment', 'Payment'),
        ('journal', 'Journal'),
        ('contra', 'Contra'),
    ]
    entry_date = models.DateField()
    voucher_no = models.CharField(max_length=30)
    voucher_type = models.CharField(max_length=10, choices=VOUCHER_TYPE_CHOICES)
    branch = models.ForeignKey('branches.Branch', on_delete=models.PROTECT)
    narration = models.TextField(blank=True)
    reference_type = models.CharField(max_length=30, blank=True)
    reference_id = models.IntegerField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='journal_entries_created'
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='journal_entries_approved',
    )
    PAYMENT_MODE_CHOICES = [
        ('cash', 'Cash'),
        ('transfer', 'Transfer'),
    ]
    payment_mode = models.CharField(max_length=10, choices=PAYMENT_MODE_CHOICES, default='cash')
    is_posted = models.BooleanField(default=True)
    is_reversed = models.BooleanField(default=False)
    reversal_of = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'journal entries'
        ordering = ['-entry_date', '-created_at']

    @property
    def total_amount(self):
        return self.lines.aggregate(t=models.Sum('debit_amount'))['t'] or 0

    def __str__(self):
        return f'{self.voucher_no} - {self.entry_date}'


class JournalLine(models.Model):
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name='lines')
    gl_account = models.ForeignKey(ChartOfAccounts, on_delete=models.PROTECT)
    debit_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    credit_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    narration = models.CharField(max_length=300, blank=True)

    def __str__(self):
        if self.debit_amount:
            return f'DR {self.gl_account.name}: {self.debit_amount}'
        return f'CR {self.gl_account.name}: {self.credit_amount}'


class InterestMaster(models.Model):
    """Period-based interest rates per account head (scheme_code)."""

    PERIOD_UNIT_CHOICES = [
        ('days', 'Days'),
        ('months', 'Months'),
        ('years', 'Years'),
    ]

    account_head = models.ForeignKey(
        ChartOfAccounts,
        on_delete=models.CASCADE,
        related_name='interest_slabs',
        help_text='GL head this rate applies to',
    )
    min_period = models.IntegerField(help_text='Minimum period (inclusive)')
    max_period = models.IntegerField(help_text='Maximum period (inclusive)')
    period_unit = models.CharField(max_length=6, choices=PERIOD_UNIT_CHOICES, default='months')
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    penal_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    senior_citizen_extra = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    widow_extra = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    ex_military_extra = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    disabled_extra = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    employee_extra = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    director_extra = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    last_posting_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['account_head', 'min_period']
        unique_together = ['account_head', 'min_period', 'max_period', 'period_unit']

    def __str__(self):
        return f'{self.account_head.code} {self.min_period}-{self.max_period} {self.period_unit}: {self.interest_rate}%'


class CashbookMaster(models.Model):
    """Daily cashbook per branch — tracks opening/closing cash balance."""

    branch = models.ForeignKey('branches.Branch', on_delete=models.PROTECT)
    txn_date = models.DateField()
    opening_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_receipts = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_payments = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    receipt_cash = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    receipt_transfer = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    payment_cash = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    payment_transfer = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    closing_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    is_closed = models.BooleanField(default=False)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['branch', 'txn_date']
        ordering = ['-txn_date']

    def __str__(self):
        return f'{self.branch.branch_code} - {self.txn_date}'
