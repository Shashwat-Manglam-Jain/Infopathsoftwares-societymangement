from django.db import models


class StandardSetup(models.Model):
    """System-level configuration (DEFAULT_SETUP_MASTER)."""

    share_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    penal_interest_code = models.CharField(max_length=10, blank=True, help_text='GL head code for penal interest')
    cash_balance_code = models.CharField(max_length=10, blank=True, help_text='GL head code for cash account')
    penal_interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    penal_charge_after_days = models.IntegerField(default=45)
    penal_on_balance = models.BooleanField(default=False)
    depreciation_fund_code = models.CharField(max_length=10, blank=True)
    depreciation_account_code = models.CharField(max_length=10, blank=True)
    profit_provision_code = models.CharField(max_length=10, blank=True)
    nominal_member_code = models.CharField(max_length=10, blank=True)
    nominal_member_fees = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_guarantees_per_person = models.IntegerField(default=2)
    taran_loan_code = models.CharField(max_length=10, blank=True)
    slip_printing_message = models.CharField(max_length=300, blank=True, default='Software By - INFOPATH SOLUTIONS')

    class Meta:
        verbose_name = 'Standard Setup'
        verbose_name_plural = 'Standard Setup'

    def __str__(self):
        return 'Standard Setup'


class SetupMaster(models.Model):
    """Deduction GL codes and default amounts (Setup_Master)."""

    shares_code = models.CharField(max_length=10, blank=True)
    shares_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    admin_fee_code = models.CharField(max_length=10, blank=True)
    admin_fee_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    misc_code = models.CharField(max_length=10, blank=True)
    misc_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    building_fund_code = models.CharField(max_length=10, blank=True)
    building_fund_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    social_welfare_code = models.CharField(max_length=10, blank=True)
    social_welfare_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    computer_fund_code = models.CharField(max_length=10, blank=True)
    computer_fund_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'Setup Master'
        verbose_name_plural = 'Setup Master'

    def __str__(self):
        return 'Setup Master'


class DescriptionMaster(models.Model):
    """Maps account head codes to transaction descriptions (DESCRIPTION_MASTER)."""

    account_head_code = models.CharField(max_length=10)
    account_head_name = models.CharField(max_length=200)
    transaction_description = models.CharField(max_length=200)

    class Meta:
        ordering = ['account_head_code']
        verbose_name = 'Description Master'

    def __str__(self):
        return f'{self.account_head_code} - {self.transaction_description}'


class JointAccountHolder(models.Model):
    """Joint account holder details."""

    account_type = models.CharField(max_length=20, help_text='savings/fd/rd/loan')
    account_id = models.IntegerField()
    name = models.CharField(max_length=200)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=15, blank=True)
    pincode = models.CharField(max_length=10, blank=True)
    sr_no = models.IntegerField(default=1)

    class Meta:
        ordering = ['sr_no']

    def __str__(self):
        return f'{self.name} - {self.account_type}'
