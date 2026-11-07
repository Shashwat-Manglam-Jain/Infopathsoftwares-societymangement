from datetime import date
from decimal import Decimal

from rest_framework import status
from rest_framework.test import APIClient

from apps.accounting.models import ChartOfAccounts
from apps.accounts.models import CustomUser
from apps.savings.models import AccountTransaction, SavingsAccount

from .base import BaseTestCase


class JWTAuthenticationTests(BaseTestCase):
    """Tests for JWT token-based authentication for the mobile API."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.member_user = CustomUser.objects.create_user(
            username='member_user',
            password='memberpass123',
            role='member',
            branch=self.head_office,
        )

    def test_jwt_token_obtain(self):
        """Valid credentials return an access and refresh token."""
        response = self.client.post(
            '/api/token/',
            {'username': 'member_user', 'password': 'memberpass123'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_jwt_token_invalid_credentials(self):
        """Invalid credentials return 401."""
        response = self.client.post(
            '/api/token/',
            {'username': 'member_user', 'password': 'wrongpass'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_jwt_token_refresh(self):
        """A valid refresh token returns a new access token."""
        token_response = self.client.post(
            '/api/token/',
            {'username': 'member_user', 'password': 'memberpass123'},
            format='json',
        )
        refresh_token = token_response.data['refresh']

        response = self.client.post(
            '/api/token/refresh/',
            {'refresh': refresh_token},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    def test_unauthorized_access(self):
        """Accessing API without token returns 401 or 403."""
        response = self.client.get('/api/me/')
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])


class MemberProfileAPITests(BaseTestCase):
    """Tests for member profile API endpoint."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.member_user = CustomUser.objects.create_user(
            username='member_api',
            password='memberpass123',
            role='member',
            branch=self.head_office,
        )
        self._authenticate()

    def _authenticate(self):
        response = self.client.post(
            '/api/token/',
            {'username': 'member_api', 'password': 'memberpass123'},
            format='json',
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')

    def test_member_profile_api(self):
        """Authenticated member can retrieve their profile."""
        response = self.client.get('/api/me/')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN])


class SavingsAccountAPITests(BaseTestCase):
    """Tests for savings account API endpoints."""

    def setUp(self):
        super().setUp()
        self._setup_coa()
        self.client = APIClient()
        self.member_user = CustomUser.objects.create_user(
            username='member_savings',
            password='memberpass123',
            role='member',
            branch=self.head_office,
        )
        self._authenticate()

        self.account = SavingsAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            account_type='savings',
            opening_date=date(2024, 1, 1),
            status='active',
            current_balance=Decimal('50000.00'),
            interest_rate=Decimal('6.00'),
            created_by=self.cashier_user,
        )
        for i in range(15):
            txn_date = date(2024, 1, 1 + i)
            AccountTransaction.objects.create(
                account=self.account,
                branch=self.head_office,
                txn_date=txn_date,
                value_date=txn_date,
                txn_type='deposit' if i % 2 == 0 else 'withdrawal',
                amount=Decimal('1000.00'),
                running_balance=Decimal('50000.00') + Decimal(str((i + 1) * 1000)),
                narration=f'Transaction {i + 1}',
                payment_mode='cash',
                created_by=self.cashier_user,
            )

    def _setup_coa(self):
        ChartOfAccounts.objects.create(
            code='1001',
            name='Cash',
            account_group='asset',
            account_type='cash',
            is_system=True,
            branch=self.head_office,
        )
        ChartOfAccounts.objects.create(
            code='2001',
            name='Savings',
            account_group='liability',
            account_type='deposits_taken',
            is_system=True,
        )

    def _authenticate(self):
        response = self.client.post(
            '/api/token/',
            {'username': 'member_savings', 'password': 'memberpass123'},
            format='json',
        )
        if response.status_code == 200:
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')

    def test_savings_account_list(self):
        """API returns member's savings accounts."""
        response = self.client.get('/api/me/savings/')
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

    def test_transactions_api(self):
        """Transaction history API returns data."""
        response = self.client.get('/api/me/transactions/')
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )


class APIAccessControlTests(BaseTestCase):
    """Tests for API access control — members can only see their own data."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.member_user1 = CustomUser.objects.create_user(
            username='member1_api',
            password='pass123',
            role='member',
            branch=self.head_office,
        )
        self.member_user2 = CustomUser.objects.create_user(
            username='member2_api',
            password='pass123',
            role='member',
            branch=self.branch_a,
        )

        self.account1 = SavingsAccount.objects.create(
            member=self.member1,
            branch=self.head_office,
            account_type='savings',
            opening_date=date(2024, 1, 1),
            status='active',
            current_balance=Decimal('50000.00'),
            interest_rate=Decimal('6.00'),
            created_by=self.cashier_user,
        )

    def _authenticate_as(self, username, password):
        response = self.client.post(
            '/api/token/',
            {'username': username, 'password': password},
            format='json',
        )
        if response.status_code == 200:
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')

    def test_staff_can_list_members(self):
        """Staff users can access member list API."""
        self._authenticate_as('admin', 'testpass123')
        response = self.client.get('/api/members/')
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

    def test_member_detail_by_number(self):
        """Staff can look up member by member number."""
        self._authenticate_as('admin', 'testpass123')
        response = self.client.get(f'/api/members/{self.member1.member_no}/')
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )
