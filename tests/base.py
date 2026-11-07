from datetime import date

from django.test import RequestFactory, TestCase

from apps.accounts.models import CustomUser
from apps.branches.models import Branch
from apps.members.models import Member


class BaseTestCase(TestCase):
    """Base test with common setup: creates branches, users, and members."""

    def setUp(self):
        self.factory = RequestFactory()

        # Branches
        self.head_office = Branch.objects.create(
            branch_code='HO',
            branch_name='Head Office',
            address='1 Main Road',
            city='Pune',
            state='Maharashtra',
            pincode='411001',
            is_head_office=True,
            status='active',
            opening_date=date(2024, 1, 1),
        )
        self.branch_a = Branch.objects.create(
            branch_code='BR01',
            branch_name='Branch A',
            address='2 MG Road',
            city='Nashik',
            state='Maharashtra',
            pincode='422001',
            is_head_office=False,
            status='active',
            opening_date=date(2024, 2, 1),
        )

        # Users
        self.admin_user = CustomUser.objects.create_user(
            username='admin',
            password='testpass123',
            email='admin@test.com',
            role='super_admin',
            branch=self.head_office,
            can_access_all_branches=True,
        )
        self.manager_user = CustomUser.objects.create_user(
            username='manager',
            password='testpass123',
            role='branch_manager',
            branch=self.head_office,
        )
        self.cashier_user = CustomUser.objects.create_user(
            username='cashier',
            password='testpass123',
            role='cashier',
            branch=self.head_office,
        )
        self.branch_cashier = CustomUser.objects.create_user(
            username='branch_cashier',
            password='testpass123',
            role='cashier',
            branch=self.branch_a,
        )
        self.accountant_user = CustomUser.objects.create_user(
            username='accountant',
            password='testpass123',
            role='accountant',
            branch=self.head_office,
        )

        # Members
        self.member1 = Member.objects.create(
            member_no='M001',
            branch=self.head_office,
            name='Rajesh Kumar',
            father_name='Suresh Kumar',
            dob=date(1985, 5, 15),
            gender='M',
            phone='9876543210',
            address='123 Main St',
            city='Pune',
            state='Maharashtra',
            pincode='411001',
            join_date=date(2024, 1, 1),
            status='active',
            category='A',
            created_by=self.admin_user,
        )
        self.member2 = Member.objects.create(
            member_no='M002',
            branch=self.branch_a,
            name='Priya Sharma',
            father_name='Amit Sharma',
            dob=date(1990, 8, 20),
            gender='F',
            phone='9876543211',
            address='456 Oak Ave',
            city='Pune',
            state='Maharashtra',
            pincode='411002',
            join_date=date(2024, 1, 15),
            status='active',
            category='A',
            created_by=self.admin_user,
        )
        self.member3 = Member.objects.create(
            member_no='M003',
            branch=self.head_office,
            name='Amit Patel',
            father_name='Ramesh Patel',
            dob=date(1975, 3, 10),
            gender='M',
            phone='9876543212',
            address='789 Park Lane',
            city='Pune',
            state='Maharashtra',
            pincode='411003',
            join_date=date(2024, 2, 1),
            status='active',
            category='B',
            created_by=self.admin_user,
        )
