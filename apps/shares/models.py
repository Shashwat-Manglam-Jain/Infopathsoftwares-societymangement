from django.conf import settings
from django.db import models


class ShareConfig(models.Model):
    face_value_per_share = models.DecimalField(max_digits=15, decimal_places=2)
    max_shares_per_member = models.PositiveIntegerField(default=100)
    min_shares_required = models.PositiveIntegerField(default=1)
    dividend_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Share Configuration'

    def __str__(self):
        return f'Share Config - Rs.{self.face_value_per_share}/share'


class ShareHolding(models.Model):
    member = models.ForeignKey('members.Member', on_delete=models.PROTECT, related_name='share_holdings')
    branch = models.ForeignKey('branches.Branch', on_delete=models.PROTECT)
    share_count = models.IntegerField(default=0)
    face_value_per_share = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    purchase_date = models.DateField()
    certificate_no = models.CharField(max_length=50, blank=True)
    meeting_no = models.CharField(max_length=20, blank=True, help_text='Board Meeting Number')
    meeting_date = models.DateField(null=True, blank=True, help_text='Board Meeting Date')
    status = models.CharField(
        max_length=15,
        choices=[
            ('active', 'Active'),
            ('transferred', 'Transferred'),
            ('surrendered', 'Surrendered'),
        ],
        default='active',
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.member.member_no} - {self.share_count} shares'


class ShareTransaction(models.Model):
    TXN_TYPE_CHOICES = [
        ('purchase', 'Purchase'),
        ('transfer', 'Transfer'),
        ('surrender', 'Surrender'),
        ('dividend', 'Dividend'),
    ]
    member = models.ForeignKey('members.Member', on_delete=models.PROTECT, related_name='share_transactions')
    branch = models.ForeignKey('branches.Branch', on_delete=models.PROTECT)
    txn_type = models.CharField(max_length=15, choices=TXN_TYPE_CHOICES)
    shares_count = models.IntegerField()
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    txn_date = models.DateField()
    narration = models.CharField(max_length=300, blank=True)
    transfer_to_member = models.ForeignKey(
        'members.Member', on_delete=models.SET_NULL, null=True, blank=True, related_name='share_transfers_received'
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-txn_date', '-created_at']

    def __str__(self):
        return f'{self.member.member_no} - {self.get_txn_type_display()} - {self.amount}'
