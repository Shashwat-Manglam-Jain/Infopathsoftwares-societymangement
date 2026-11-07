from django.conf import settings
from django.db import models


class FinancialYear(models.Model):
    fy_code = models.CharField(max_length=10, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
    is_closed = models.BooleanField(default=False)
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return self.fy_code


class WorkingDay(models.Model):
    """Controls the transaction date for each branch. Must be set before any transaction."""

    branch = models.OneToOneField('branches.Branch', on_delete=models.PROTECT, related_name='working_day')
    current_date = models.DateField()
    last_working_date = models.DateField(null=True, blank=True)
    is_day_open = models.BooleanField(default=False)
    day_end_completed = models.BooleanField(default=False)
    cashbook_posted = models.BooleanField(default=False)
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='days_opened',
    )
    opened_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'{self.branch.branch_name} - {self.current_date} ({"Open" if self.is_day_open else "Closed"})'


class DayEndLog(models.Model):
    STATUS_CHOICES = [
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('rolled_back', 'Rolled Back'),
    ]
    branch = models.ForeignKey('branches.Branch', on_delete=models.PROTECT)
    processing_date = models.DateField()
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='running')
    savings_interest_accrued_count = models.IntegerField(default=0)
    loan_interest_accrued_count = models.IntegerField(default=0)
    loans_marked_overdue_count = models.IntegerField(default=0)
    loans_marked_npa_count = models.IntegerField(default=0)
    cashbook_entries_posted = models.IntegerField(default=0)
    pigmmy_collections_posted = models.IntegerField(default=0)
    error_log = models.TextField(blank=True)
    run_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-processing_date']
        unique_together = ['branch', 'processing_date']

    def __str__(self):
        return f'{self.branch.branch_name} - {self.processing_date} - {self.status}'


class MonthEndLog(models.Model):
    """Monthly processing: loan demand generation, interest calculation."""

    STATUS_CHOICES = [
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    branch = models.ForeignKey('branches.Branch', on_delete=models.PROTECT)
    month = models.DateField(help_text='First day of the month')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='running')
    loan_interest_calculated_count = models.IntegerField(default=0)
    demand_generated_count = models.IntegerField(default=0)
    rd_installments_due_count = models.IntegerField(default=0)
    run_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_log = models.TextField(blank=True)

    class Meta:
        ordering = ['-month']
        unique_together = ['branch', 'month']

    def __str__(self):
        return f'{self.branch.branch_name} - {self.month.strftime("%b %Y")} - {self.status}'


class YearEndLog(models.Model):
    """Year-end processing: P&L zeroing, opening balance update."""

    STATUS_CHOICES = [
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    financial_year = models.ForeignKey(FinancialYear, on_delete=models.PROTECT)
    branch = models.ForeignKey('branches.Branch', on_delete=models.PROTECT)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='running')
    pl_accounts_zeroed = models.IntegerField(default=0)
    opening_balances_updated = models.IntegerField(default=0)
    profit_or_loss = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    run_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_log = models.TextField(blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f'{self.financial_year.fy_code} - {self.branch.branch_name} - {self.status}'
