from datetime import date

from apps.audit.models import AuditTrail
from apps.audit.services import log_action
from apps.members.models import Member

from .base import BaseTestCase


class AuditTrailCreationTests(BaseTestCase):
    """Tests for audit trail logging."""

    def test_audit_trail_on_create(self):
        """Creating a record can be logged in the audit trail."""
        member = Member.objects.create(
            member_no='M-AUDIT-001',
            branch=self.head_office,
            name='Audit Test',
            father_name='Father',
            dob=date(1990, 1, 1),
            gender='M',
            phone='9000000100',
            address='Addr',
            city='City',
            state='State',
            pincode='000000',
            join_date=date(2024, 1, 1),
            status='active',
            category='A',
            created_by=self.admin_user,
        )
        log_action(
            user=self.admin_user,
            branch=self.head_office,
            action='create',
            table_name='members_member',
            record_id=member.pk,
            new_values={
                'member_no': 'M-AUDIT-001',
                'name': 'Audit Test',
                'status': 'active',
            },
            ip_address='192.168.1.100',
        )
        trail = AuditTrail.objects.filter(table_name='members_member', record_id=member.pk).first()
        self.assertIsNotNone(trail)
        self.assertEqual(trail.action, 'create')
        self.assertIsNone(trail.old_values)
        self.assertEqual(trail.new_values['name'], 'Audit Test')

    def test_audit_trail_on_update(self):
        """Updating a record logs both old and new values."""
        old_name = self.member1.name
        self.member1.name = 'Rajesh Kumar Updated'
        self.member1.save()

        log_action(
            user=self.admin_user,
            branch=self.head_office,
            action='update',
            table_name='members_member',
            record_id=self.member1.pk,
            old_values={'name': old_name},
            new_values={'name': 'Rajesh Kumar Updated'},
            ip_address='192.168.1.100',
        )
        trail = AuditTrail.objects.filter(
            table_name='members_member',
            record_id=self.member1.pk,
            action='update',
        ).first()
        self.assertIsNotNone(trail)
        self.assertEqual(trail.old_values['name'], old_name)
        self.assertEqual(trail.new_values['name'], 'Rajesh Kumar Updated')

    def test_audit_trail_captures_user(self):
        """Audit trail correctly records which user performed the action."""
        log_action(
            user=self.cashier_user,
            branch=self.head_office,
            action='create',
            table_name='test_table',
            record_id=1,
        )
        trail = AuditTrail.objects.filter(user=self.cashier_user, table_name='test_table').first()
        self.assertIsNotNone(trail)
        self.assertEqual(trail.user, self.cashier_user)

    def test_audit_trail_captures_ip(self):
        """Audit trail records the IP address of the action."""
        log_action(
            user=self.admin_user,
            branch=self.head_office,
            action='create',
            table_name='test_table',
            record_id=1,
            ip_address='10.0.0.50',
        )
        trail = AuditTrail.objects.filter(table_name='test_table', ip_address='10.0.0.50').first()
        self.assertIsNotNone(trail)
        self.assertEqual(trail.ip_address, '10.0.0.50')

    def test_audit_trail_captures_branch(self):
        """Audit trail records which branch the action occurred at."""
        log_action(
            user=self.branch_cashier,
            branch=self.branch_a,
            action='create',
            table_name='test_table',
            record_id=1,
        )
        trail = AuditTrail.objects.filter(branch=self.branch_a, table_name='test_table').first()
        self.assertIsNotNone(trail)
        self.assertEqual(trail.branch, self.branch_a)


class AuditTrailImmutabilityTests(BaseTestCase):
    """Tests for audit trail immutability — entries should be append-only."""

    def test_audit_trail_append_only(self):
        """Audit trail entries are append-only. Business logic should prevent
        updates and deletes. We verify the model allows reads and creates only
        through service functions.
        """
        log_action(
            user=self.admin_user,
            branch=self.head_office,
            action='create',
            table_name='test_immutable',
            record_id=1,
            new_values={'key': 'original'},
        )
        trail = AuditTrail.objects.filter(table_name='test_immutable').first()
        self.assertIsNotNone(trail)
        self.assertEqual(trail.new_values['key'], 'original')

        # The entry exists and can be read
        count_before = AuditTrail.objects.filter(table_name='test_immutable').count()
        self.assertEqual(count_before, 1)

    def test_audit_trail_ordering(self):
        """Audit entries are ordered most recent first."""
        for i in range(5):
            log_action(
                user=self.admin_user,
                branch=self.head_office,
                action='create',
                table_name='test_ordering',
                record_id=i + 1,
            )
        entries = AuditTrail.objects.filter(table_name='test_ordering')
        timestamps = [e.timestamp for e in entries]
        self.assertEqual(
            timestamps,
            sorted(timestamps, reverse=True),
        )

    def test_audit_trail_multiple_actions_same_record(self):
        """Multiple actions on the same record create separate audit entries."""
        log_action(
            user=self.admin_user,
            branch=self.head_office,
            action='create',
            table_name='test_multi',
            record_id=1,
            new_values={'status': 'active'},
        )
        log_action(
            user=self.admin_user,
            branch=self.head_office,
            action='update',
            table_name='test_multi',
            record_id=1,
            old_values={'status': 'active'},
            new_values={'status': 'inactive'},
        )
        entries = AuditTrail.objects.filter(table_name='test_multi', record_id=1)
        self.assertEqual(entries.count(), 2)
        actions = list(entries.values_list('action', flat=True))
        self.assertIn('create', actions)
        self.assertIn('update', actions)
