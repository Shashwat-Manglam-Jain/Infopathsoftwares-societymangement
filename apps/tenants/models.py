from django.db import models
from django_tenants.models import DomainMixin, TenantMixin


class Society(TenantMixin):
    name = models.CharField(max_length=255)
    registration_no = models.CharField(max_length=100, blank=True)
    registration_date = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=10, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    fax = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    name_regional = models.CharField(max_length=500, blank=True, help_text='Name in regional language (Marathi/Hindi)')

    pan_no = models.CharField(max_length=10, blank=True)
    tan_no = models.CharField(max_length=10, blank=True)
    gst_no = models.CharField(max_length=15, blank=True)
    authorized_capital = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    paid_up_capital = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    share_nominal_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    registration_authority = models.CharField(max_length=200, blank=True)
    society_category = models.CharField(max_length=100, blank=True)
    logo = models.ImageField(upload_to='society/logos/', blank=True)

    society_type = models.CharField(
        max_length=30,
        choices=[
            ('credit_cooperative', 'Credit Cooperative Society'),
            ('multistate', 'Multistate Cooperative Society'),
            ('nidhi', 'Nidhi Company'),
            ('thrift', 'Thrift & Credit Society'),
        ],
        default='credit_cooperative',
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    auto_create_schema = True

    class Meta:
        verbose_name_plural = 'societies'

    def __str__(self):
        return self.name


class Domain(DomainMixin):
    pass


class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=100)
    max_members = models.IntegerField()
    max_users = models.IntegerField()
    max_branches = models.IntegerField(default=1)
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2)
    features = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.name} - Rs.{self.price_monthly}/mo'


class Subscription(models.Model):
    society = models.OneToOneField(Society, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_trial = models.BooleanField(default=True)
    razorpay_subscription_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('trial', 'Trial'),
            ('active', 'Active'),
            ('past_due', 'Past Due'),
            ('cancelled', 'Cancelled'),
        ],
        default='trial',
    )

    @property
    def is_expired(self):
        from datetime import date

        if self.status == 'cancelled':
            return True
        if self.end_date and self.end_date < date.today():
            return True
        return False

    @property
    def days_remaining(self):
        from datetime import date

        if not self.end_date:
            return None
        return max(0, (self.end_date - date.today()).days)

    def __str__(self):
        return f'{self.society.name} - {self.plan.name} ({self.status})'
