from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class LoanProduct(models.Model):
    INTEREST_TYPE_CHOICES = [
        ('flat', 'Flat'),
        ('reducing_monthly', 'Reducing Balance (Monthly)'),
        ('reducing_daily', 'Reducing Balance (Daily)'),
        ('compound', 'Compound'),
    ]
    LOAN_CATEGORY_CHOICES = [
        ('non_mortgage', 'Non-Mortgage Loan'),
        ('mortgage', 'Mortgage Loan'),
    ]
    MORTGAGE_TYPE_CHOICES = [
        ('none', 'None'),
        ('fixed_deposit', 'Against Fixed Deposit'),
        ('pigmmy', 'Against Pigmmy/Daily Deposit'),
        ('gold', 'Against Gold'),
        ('property', 'Property Mortgage'),
        ('vehicle', 'Against Vehicle'),
        ('other', 'Other Mortgage'),
    ]

    name = models.CharField(max_length=100)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    max_amount = models.DecimalField(max_digits=15, decimal_places=2)
    max_tenure_months = models.IntegerField()
    interest_type = models.CharField(max_length=20, choices=INTEREST_TYPE_CHOICES, default='reducing_monthly')
    loan_category = models.CharField(max_length=15, choices=LOAN_CATEGORY_CHOICES, default='non_mortgage')
    mortgage_type = models.CharField(max_length=20, choices=MORTGAGE_TYPE_CHOICES, default='none')
    allow_multiple = models.BooleanField(
        default=False,
        help_text='Mortgage loans allow multiple active loans. Non-mortgage: only one active at a time.',
    )
    requires_guarantor = models.BooleanField(default=True)
    min_guarantors = models.IntegerField(default=1)
    max_guarantors = models.IntegerField(default=2)
    guarantor_must_be_shareholder = models.BooleanField(
        default=True,
        help_text='Guarantor must have active share account',
    )
    requires_director_recommendation = models.BooleanField(default=False)
    requires_collateral = models.BooleanField(default=False)
    max_loan_to_deposit_ratio = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='For loans against FD/pigmmy: max % of deposit amount (e.g., 90)',
    )
    processing_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    penal_interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    npa_days_threshold = models.IntegerField(default=90)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.name} ({self.interest_rate}%)'


class LoanAccount(models.Model):
    STATUS_CHOICES = [
        ('applied', 'Applied'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('disbursed', 'Disbursed'),
        ('closed', 'Closed'),
        ('written_off', 'Written Off'),
        ('npa', 'NPA'),
    ]
    CLOSURE_TYPE_CHOICES = [
        ('normal', 'Normal Closure'),
        ('prepayment', 'Prepayment'),
        ('write_off', 'Write Off'),
    ]

    member = models.ForeignKey('members.Member', on_delete=models.PROTECT, related_name='loan_accounts')
    branch = models.ForeignKey('branches.Branch', on_delete=models.PROTECT)
    loan_product = models.ForeignKey(LoanProduct, on_delete=models.PROTECT)
    loan_no = models.CharField(max_length=20, unique=True)
    ledger_number = models.PositiveBigIntegerField(null=True, blank=True)
    folio_number = models.CharField(max_length=10, blank=True)
    gl_head = models.ForeignKey(
        'accounting.ChartOfAccounts',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='loan_accounts',
        help_text='GL head this loan belongs to',
    )
    applied_date = models.DateField()
    applied_amount = models.DecimalField(max_digits=15, decimal_places=2)
    approved_date = models.DateField(null=True, blank=True)
    approved_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_loans'
    )
    disbursed_date = models.DateField(null=True, blank=True)
    disbursed_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    penal_interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tenure_months = models.IntegerField()
    emi_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    date_of_first_recovery = models.DateField(null=True, blank=True)
    loan_expiry_date = models.DateField(null=True, blank=True)
    total_interest_payable = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    outstanding_principal = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    outstanding_interest = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    bal_repayment = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, help_text='Balance repayment remaining'
    )
    bal_interest = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, help_text='Balance interest remaining'
    )
    bal_penal = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text='Balance penal interest')
    bal_others = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text='Other outstanding charges')
    overdue_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    overdue_days = models.IntegerField(default=0)
    last_interest_calculated_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='applied')
    closure_date = models.DateField(null=True, blank=True)
    closure_type = models.CharField(max_length=15, choices=CLOSURE_TYPE_CHOICES, blank=True)
    remarks = models.TextField(blank=True)

    sign = models.IntegerField(default=0, help_text='1=debit nature, -1=credit nature, 0=default')

    # InfoSociety extended fields
    loan_form_no = models.CharField(max_length=20, blank=True)
    meeting_no = models.CharField(max_length=20, blank=True, help_text='Board Meeting Number')
    meeting_date = models.DateField(null=True, blank=True, help_text='Board Meeting Date')
    sanction_date = models.DateField(null=True, blank=True)
    sanction_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    sanctioned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='loans_sanctioned',
    )
    director_recommendation = models.ForeignKey(
        'members.Member',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='loans_recommended',
        help_text='Director who recommended this loan (must have is_director=True)',
    )
    mortgage_account_no = models.CharField(
        max_length=20,
        blank=True,
        help_text='FD/Pigmmy account number used as mortgage',
    )
    mortgage_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    notice_issued = models.BooleanField(default=False)
    notice_date = models.DateField(null=True, blank=True)
    court_case = models.BooleanField(default=False)
    court_case_details = models.TextField(blank=True)
    pending_installments = models.IntegerField(default=0)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='loans_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-applied_date']

    def __str__(self):
        return f'{self.loan_no} - {self.member.name} - {self.disbursed_amount or self.applied_amount}'

    def clean(self):
        if self.director_recommendation and not self.director_recommendation.is_director:
            raise ValidationError(
                {
                    'director_recommendation': 'Selected member must be a board director.',
                }
            )
        if (
            self.loan_product
            and not self.loan_product.allow_multiple
            and self.status in ('applied', 'approved', 'disbursed')
        ):
            qs = LoanAccount.objects.filter(
                member=self.member,
                loan_product=self.loan_product,
                status__in=['applied', 'approved', 'disbursed', 'npa'],
            )
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError(
                    'Member already has an active non-mortgage loan of this type. '
                    'Close existing loan before opening a new one.'
                )


class LoanGuarantor(models.Model):
    loan = models.ForeignKey(LoanAccount, on_delete=models.CASCADE, related_name='guarantors')
    guarantor_member = models.ForeignKey('members.Member', on_delete=models.PROTECT, related_name='guaranteed_loans')
    guarantee_amount = models.DecimalField(max_digits=15, decimal_places=2)
    guarantor_share_account = models.CharField(
        max_length=20,
        blank=True,
        help_text='Share account number of guarantor',
    )

    def __str__(self):
        return f'{self.guarantor_member.name} for {self.loan.loan_no}'

    def clean(self):
        from apps.shares.models import ShareHolding

        if not ShareHolding.objects.filter(
            member=self.guarantor_member,
            status='active',
        ).exists():
            raise ValidationError('Guarantor must have an active share holding.')

    @staticmethod
    def active_guarantee_count(member):
        """Count active loans where this member is guarantor (non-zero balance only)."""
        return LoanGuarantor.objects.filter(
            guarantor_member=member,
            loan__status__in=['disbursed', 'npa'],
            loan__outstanding_principal__gt=0,
        ).count()


class LoanCollateral(models.Model):
    COLLATERAL_TYPE_CHOICES = [
        ('gold', 'Gold'),
        ('property', 'Property'),
        ('fd', 'Fixed Deposit'),
        ('vehicle', 'Vehicle'),
        ('other', 'Other'),
    ]
    loan = models.ForeignKey(LoanAccount, on_delete=models.CASCADE, related_name='collaterals')
    collateral_type = models.CharField(max_length=15, choices=COLLATERAL_TYPE_CHOICES)
    description = models.TextField()
    estimated_value = models.DecimalField(max_digits=15, decimal_places=2)
    document = models.FileField(upload_to='loans/collaterals/', blank=True)
    status = models.CharField(
        max_length=10,
        choices=[('pledged', 'Pledged'), ('released', 'Released')],
        default='pledged',
    )

    def __str__(self):
        return f'{self.get_collateral_type_display()} - {self.estimated_value}'


class EMISchedule(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('partially_paid', 'Partially Paid'),
    ]
    loan = models.ForeignKey(LoanAccount, on_delete=models.CASCADE, related_name='emi_schedule')
    installment_no = models.IntegerField()
    due_date = models.DateField()
    principal_component = models.DecimalField(max_digits=15, decimal_places=2)
    interest_component = models.DecimalField(max_digits=15, decimal_places=2)
    total_emi = models.DecimalField(max_digits=15, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    paid_date = models.DateField(null=True, blank=True)
    penalty_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    branch = models.ForeignKey('branches.Branch', on_delete=models.PROTECT, null=True, blank=True)

    class Meta:
        ordering = ['due_date']
        unique_together = ['loan', 'installment_no']

    def __str__(self):
        return f'{self.loan.loan_no} - EMI #{self.installment_no}'


class LoanRepayment(models.Model):
    loan = models.ForeignKey(LoanAccount, on_delete=models.PROTECT, related_name='repayments')
    branch = models.ForeignKey('branches.Branch', on_delete=models.PROTECT)
    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    principal_adjusted = models.DecimalField(max_digits=15, decimal_places=2)
    interest_adjusted = models.DecimalField(max_digits=15, decimal_places=2)
    penalty_adjusted = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    excess_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    payment_mode = models.CharField(max_length=10, default='cash')
    receipt_no = models.CharField(max_length=30, blank=True)
    emi_schedule = models.ForeignKey(EMISchedule, on_delete=models.SET_NULL, null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-payment_date']

    def __str__(self):
        return f'{self.loan.loan_no} - {self.amount} on {self.payment_date}'


class StandingInstruction(models.Model):
    """Charge fees/penalties to loan accounts (form fees, legal fees, court fees, etc.)."""

    CHARGE_TYPE_CHOICES = [
        ('form_fees', 'Loan Form Fees'),
        ('legal_fees', 'Legal/Advocate Fees'),
        ('court_fees', 'Court Fees'),
        ('insurance', 'Insurance Premium'),
        ('stamp_duty', 'Stamp Duty'),
        ('notice_fees', 'Notice Fees'),
        ('other', 'Other Charges'),
    ]

    loan = models.ForeignKey(LoanAccount, on_delete=models.PROTECT, related_name='standing_instructions')
    branch = models.ForeignKey('branches.Branch', on_delete=models.PROTECT)
    charge_type = models.CharField(max_length=20, choices=CHARGE_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    charge_date = models.DateField()
    narration = models.CharField(max_length=300)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-charge_date']

    def __str__(self):
        return f'{self.loan.loan_no} - {self.get_charge_type_display()} - {self.amount}'
