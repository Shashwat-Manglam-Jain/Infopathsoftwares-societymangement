from decimal import Decimal

from django.conf import settings
from django.db import models


class Member(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('deceased', 'Deceased'),
        ('expelled', 'Expelled'),
    ]
    CATEGORY_CHOICES = [('A', 'Category A'), ('B', 'Category B'), ('C', 'Category C')]
    GENDER_CHOICES = [('male', 'Male'), ('female', 'Female'), ('other', 'Other')]

    member_no = models.CharField(max_length=20, unique=True)
    branch = models.ForeignKey('branches.Branch', on_delete=models.PROTECT, related_name='members')
    name = models.CharField(max_length=200)
    father_name = models.CharField(max_length=200, blank=True)
    mother_name = models.CharField(max_length=200, blank=True)
    dob = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    marital_status = models.CharField(max_length=20, blank=True)
    aadhar_no = models.CharField(max_length=12, blank=True)
    pan_no = models.CharField(max_length=10, blank=True)
    voter_id = models.CharField(max_length=20, blank=True)
    phone = models.CharField(max_length=15)
    alt_phone = models.CharField(max_length=15, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=10, blank=True)
    occupation = models.CharField(max_length=100, blank=True)
    monthly_income = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    join_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    exit_date = models.DateField(null=True, blank=True, help_text='Date when member left/deceased/expelled')
    category = models.CharField(max_length=1, choices=CATEGORY_CHOICES, default='A')
    photo = models.ImageField(upload_to='members/photos/', blank=True)
    signature = models.ImageField(upload_to='members/signatures/', blank=True)
    kyc_verified = models.BooleanField(default=False)
    kyc_date = models.DateField(null=True, blank=True)
    # Special category flags (affect interest rates and reporting)
    is_director = models.BooleanField(default=False, help_text='Is board director of the society')
    is_employee = models.BooleanField(default=False, help_text='Is employee of the society')
    is_minor = models.BooleanField(default=False)
    is_senior_citizen = models.BooleanField(default=False, help_text='Age 60+, gets extra FD interest')
    is_widow = models.BooleanField(default=False)
    is_physically_disabled = models.BooleanField(default=False)
    is_ex_military = models.BooleanField(default=False)
    is_nominal_member = models.BooleanField(default=False)
    guardian_name = models.CharField(max_length=200, blank=True, help_text='Required if minor')
    guardian_address = models.TextField(blank=True)
    introducer = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='introduced_members',
        help_text='Existing member who introduced this member',
    )

    # Extended profile fields
    prefix = models.CharField(max_length=10, blank=True, help_text='Mr./Mrs./Ms./Dr./Shri/Smt')
    name_regional = models.CharField(max_length=500, blank=True, help_text='Name in regional language (Marathi/Hindi)')
    district = models.CharField(max_length=100, blank=True)
    tahsil = models.CharField(max_length=100, blank=True)
    blood_group = models.CharField(max_length=5, blank=True)
    education = models.CharField(max_length=50, blank=True)
    religion = models.CharField(max_length=30, blank=True)
    caste = models.CharField(max_length=50, blank=True)
    driving_licence_no = models.CharField(max_length=20, blank=True)
    post = models.CharField(max_length=100, blank=True)
    area = models.CharField(max_length=100, blank=True)
    sub_area = models.CharField(max_length=100, blank=True)
    city_village = models.CharField(max_length=100, blank=True)
    info = models.CharField(max_length=256, blank=True, help_text='Additional information')

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='members_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['member_no']

    def __str__(self):
        return f'{self.member_no} - {self.name}'

    def get_fd_interest_bonus(self):
        """Extra interest rate percentage for special categories on FD."""
        bonus = Decimal('0.00')
        if self.is_senior_citizen:
            bonus = max(bonus, Decimal('0.50'))
        if self.is_widow:
            bonus = max(bonus, Decimal('0.50'))
        if self.is_ex_military:
            bonus = max(bonus, Decimal('0.25'))
        if self.is_physically_disabled:
            bonus = max(bonus, Decimal('0.25'))
        if self.is_employee:
            bonus = max(bonus, Decimal('0.25'))
        if self.is_director:
            bonus = max(bonus, Decimal('0.25'))
        return bonus


class MemberNominee(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='nominees')
    name = models.CharField(max_length=200)
    relation = models.CharField(max_length=50)
    dob = models.DateField(null=True, blank=True)
    aadhar_no = models.CharField(max_length=12, blank=True)
    phone = models.CharField(max_length=15, blank=True)
    share_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    is_primary = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.name} ({self.relation}) - {self.member.member_no}'


class MemberDocument(models.Model):
    DOC_TYPE_CHOICES = [
        ('aadhar', 'Aadhaar Card'),
        ('pan', 'PAN Card'),
        ('photo', 'Photograph'),
        ('signature', 'Signature'),
        ('address_proof', 'Address Proof'),
        ('other', 'Other'),
    ]
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=20, choices=DOC_TYPE_CHOICES)
    file = models.FileField(upload_to='members/documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'{self.member.member_no} - {self.get_document_type_display()}'
