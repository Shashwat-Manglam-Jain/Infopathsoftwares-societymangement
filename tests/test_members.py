from datetime import date
from decimal import Decimal

from django.db import IntegrityError

from apps.members.models import Member, MemberDocument, MemberNominee

from .base import BaseTestCase


class MemberCreationTests(BaseTestCase):
    """Tests for member registration and data integrity."""

    def test_create_member(self):
        """Creating a member persists all fields correctly."""
        member = Member.objects.create(
            member_no='M100',
            branch=self.head_office,
            name='Test Member',
            father_name='Test Father',
            dob=date(1992, 6, 15),
            gender='M',
            marital_status='single',
            aadhar_no='123456789012',
            pan_no='ABCDE1234F',
            phone='9000000001',
            address='Test Address',
            city='Mumbai',
            state='Maharashtra',
            pincode='400001',
            occupation='Business',
            monthly_income=Decimal('50000.00'),
            join_date=date(2024, 3, 1),
            status='active',
            category='A',
            created_by=self.admin_user,
        )
        member.refresh_from_db()
        self.assertEqual(member.member_no, 'M100')
        self.assertEqual(member.name, 'Test Member')
        self.assertEqual(member.branch, self.head_office)
        self.assertEqual(member.monthly_income, Decimal('50000.00'))
        self.assertEqual(member.status, 'active')

    def test_member_unique_member_no(self):
        """member_no must be unique across the society."""
        with self.assertRaises(IntegrityError):
            Member.objects.create(
                member_no='M001',  # duplicate
                branch=self.head_office,
                name='Duplicate',
                father_name='Father',
                dob=date(1990, 1, 1),
                gender='M',
                phone='9000000099',
                address='Addr',
                city='City',
                state='State',
                pincode='000000',
                join_date=date(2024, 1, 1),
                status='active',
                category='A',
                created_by=self.admin_user,
            )

    def test_member_belongs_to_branch(self):
        """A member is associated with exactly one home branch."""
        self.assertEqual(self.member1.branch, self.head_office)
        self.assertEqual(self.member2.branch, self.branch_a)

    def test_member_status_transitions(self):
        """Member status can transition through lifecycle states."""
        self.member1.status = 'inactive'
        self.member1.save()
        self.member1.refresh_from_db()
        self.assertEqual(self.member1.status, 'inactive')

        self.member1.status = 'deceased'
        self.member1.exit_date = date(2025, 6, 1)
        self.member1.save()
        self.member1.refresh_from_db()
        self.assertEqual(self.member1.status, 'deceased')
        self.assertEqual(self.member1.exit_date, date(2025, 6, 1))

    def test_member_str(self):
        """String representation includes member_no and name."""
        expected = 'M001 - Rajesh Kumar'
        self.assertEqual(str(self.member1), expected)


class MemberNomineeTests(BaseTestCase):
    """Tests for nominee management."""

    def test_create_nominee(self):
        """A nominee can be assigned to a member."""
        nominee = MemberNominee.objects.create(
            member=self.member1,
            name='Sita Kumar',
            relation='wife',
            dob=date(1988, 3, 20),
            phone='9876500001',
            share_percentage=Decimal('100.00'),
            is_primary=True,
        )
        self.assertEqual(nominee.member, self.member1)
        self.assertEqual(nominee.share_percentage, Decimal('100.00'))
        self.assertTrue(nominee.is_primary)

    def test_multiple_nominees_percentage(self):
        """Multiple nominees' share_percentage values should be individually valid."""
        MemberNominee.objects.create(
            member=self.member1,
            name='Sita Kumar',
            relation='wife',
            dob=date(1988, 3, 20),
            phone='9876500001',
            share_percentage=Decimal('60.00'),
            is_primary=True,
        )
        MemberNominee.objects.create(
            member=self.member1,
            name='Rahul Kumar',
            relation='son',
            dob=date(2010, 7, 5),
            phone='9876500002',
            share_percentage=Decimal('40.00'),
            is_primary=False,
        )
        nominees = MemberNominee.objects.filter(member=self.member1)
        total_pct = sum(n.share_percentage for n in nominees)
        self.assertEqual(total_pct, Decimal('100.00'))

    def test_nominee_relation_to_member(self):
        """Deleting a member cascades to nominees."""
        MemberNominee.objects.create(
            member=self.member3,
            name='Nominee X',
            relation='spouse',
            dob=date(1980, 1, 1),
            share_percentage=Decimal('100.00'),
            is_primary=True,
        )
        member_id = self.member3.pk
        self.member3.delete()
        self.assertFalse(MemberNominee.objects.filter(member_id=member_id).exists())


class MemberSearchTests(BaseTestCase):
    """Tests for member search and filtering."""

    def test_search_by_name(self):
        """Members can be found by partial name match."""
        results = Member.objects.filter(name__icontains='Rajesh')
        self.assertEqual(results.count(), 1)
        self.assertEqual(results.first(), self.member1)

    def test_search_by_phone(self):
        """Members can be found by phone number."""
        results = Member.objects.filter(phone='9876543211')
        self.assertEqual(results.count(), 1)
        self.assertEqual(results.first(), self.member2)

    def test_search_by_member_no(self):
        """Members can be found by their member number."""
        results = Member.objects.filter(member_no='M001')
        self.assertEqual(results.count(), 1)
        self.assertEqual(results.first(), self.member1)

    def test_filter_by_branch(self):
        """Filtering by branch returns only members of that branch."""
        ho_members = Member.objects.filter(branch=self.head_office)
        br_members = Member.objects.filter(branch=self.branch_a)
        self.assertEqual(ho_members.count(), 2)  # member1, member3
        self.assertEqual(br_members.count(), 1)  # member2

    def test_filter_by_status(self):
        """Filtering by status works correctly."""
        self.member3.status = 'inactive'
        self.member3.save()
        active = Member.objects.filter(status='active')
        inactive = Member.objects.filter(status='inactive')
        self.assertEqual(active.count(), 2)
        self.assertEqual(inactive.count(), 1)

    def test_filter_by_category(self):
        """Filtering by category works correctly."""
        cat_a = Member.objects.filter(category='A')
        cat_b = Member.objects.filter(category='B')
        self.assertEqual(cat_a.count(), 2)
        self.assertEqual(cat_b.count(), 1)


class MemberKYCTests(BaseTestCase):
    """Tests for KYC verification workflow."""

    def test_kyc_initially_unverified(self):
        """New members start with KYC unverified."""
        self.assertFalse(self.member1.kyc_verified)

    def test_kyc_verification(self):
        """KYC can be marked as verified with a date."""
        self.member1.kyc_verified = True
        self.member1.kyc_date = date(2024, 2, 1)
        self.member1.save()
        self.member1.refresh_from_db()
        self.assertTrue(self.member1.kyc_verified)
        self.assertEqual(self.member1.kyc_date, date(2024, 2, 1))

    def test_member_document_upload(self):
        """Documents can be attached to a member."""
        doc = MemberDocument.objects.create(
            member=self.member1,
            document_type='aadhar',
            file='documents/member1_aadhar.pdf',
        )
        self.assertEqual(doc.member, self.member1)
        self.assertEqual(doc.document_type, 'aadhar')
        self.assertIsNone(doc.verified_by)

    def test_document_verification(self):
        """Documents can be verified by a user."""
        doc = MemberDocument.objects.create(
            member=self.member1,
            document_type='pan',
            file='documents/member1_pan.pdf',
        )
        doc.verified_by = self.admin_user
        doc.verified_at = date(2024, 2, 15)
        doc.save()
        doc.refresh_from_db()
        self.assertEqual(doc.verified_by, self.admin_user)


class MemberCategoryFlagsTests(BaseTestCase):
    """Tests for special member category flags and their effect on FD interest."""

    def test_default_flags_are_false(self):
        """All category flags default to False on new members."""
        self.assertFalse(self.member1.is_director)
        self.assertFalse(self.member1.is_employee)
        self.assertFalse(self.member1.is_minor)
        self.assertFalse(self.member1.is_senior_citizen)
        self.assertFalse(self.member1.is_widow)
        self.assertFalse(self.member1.is_physically_disabled)
        self.assertFalse(self.member1.is_ex_military)

    def test_set_senior_citizen_flag(self):
        self.member1.is_senior_citizen = True
        self.member1.save()
        self.member1.refresh_from_db()
        self.assertTrue(self.member1.is_senior_citizen)

    def test_set_widow_flag(self):
        self.member2.is_widow = True
        self.member2.save()
        self.member2.refresh_from_db()
        self.assertTrue(self.member2.is_widow)

    def test_set_director_flag(self):
        self.member1.is_director = True
        self.member1.save()
        self.member1.refresh_from_db()
        self.assertTrue(self.member1.is_director)

    def test_set_employee_flag(self):
        self.member1.is_employee = True
        self.member1.save()
        self.member1.refresh_from_db()
        self.assertTrue(self.member1.is_employee)

    def test_set_minor_with_guardian(self):
        self.member1.is_minor = True
        self.member1.guardian_name = 'Parent Name'
        self.member1.guardian_address = 'Parent Address'
        self.member1.save()
        self.member1.refresh_from_db()
        self.assertTrue(self.member1.is_minor)
        self.assertEqual(self.member1.guardian_name, 'Parent Name')

    def test_set_physically_disabled_flag(self):
        self.member1.is_physically_disabled = True
        self.member1.save()
        self.member1.refresh_from_db()
        self.assertTrue(self.member1.is_physically_disabled)

    def test_set_ex_military_flag(self):
        self.member1.is_ex_military = True
        self.member1.save()
        self.member1.refresh_from_db()
        self.assertTrue(self.member1.is_ex_military)

    def test_introducer_fk(self):
        """A member can have an introducer (another member)."""
        self.member2.introducer = self.member1
        self.member2.save()
        self.member2.refresh_from_db()
        self.assertEqual(self.member2.introducer, self.member1)
        self.assertIn(self.member2, self.member1.introduced_members.all())


class MemberExtendedProfileTests(BaseTestCase):
    """Tests for extended profile fields (prefix, regional name, district, etc.)."""

    def test_extended_profile_fields(self):
        member = Member.objects.create(
            member_no='M200',
            branch=self.head_office,
            name='Sunita Devi',
            father_name='Ram Prasad',
            dob=date(1970, 1, 1),
            gender='female',
            phone='9000000200',
            join_date=date(2024, 1, 1),
            status='active',
            category='A',
            created_by=self.admin_user,
            prefix='Smt',
            name_regional='सुनीत௦ देवी',
            district='Pune',
            tahsil='Haveli',
            blood_group='O+',
            education='Graduate',
            religion='Hindu',
            caste='General',
            driving_licence_no='MH1220210001234',
        )
        member.refresh_from_db()
        self.assertEqual(member.prefix, 'Smt')
        self.assertEqual(member.district, 'Pune')
        self.assertEqual(member.tahsil, 'Haveli')
        self.assertEqual(member.blood_group, 'O+')
        self.assertEqual(member.education, 'Graduate')
        self.assertEqual(member.religion, 'Hindu')
        self.assertEqual(member.caste, 'General')
        self.assertEqual(member.driving_licence_no, 'MH1220210001234')

    def test_extended_fields_are_optional(self):
        """All extended profile fields should be blank by default."""
        self.assertEqual(self.member1.prefix, '')
        self.assertEqual(self.member1.name_regional, '')
        self.assertEqual(self.member1.district, '')
        self.assertEqual(self.member1.tahsil, '')
        self.assertEqual(self.member1.blood_group, '')
        self.assertEqual(self.member1.education, '')
        self.assertEqual(self.member1.religion, '')
        self.assertEqual(self.member1.caste, '')
        self.assertEqual(self.member1.driving_licence_no, '')


class MemberFDInterestBonusTests(BaseTestCase):
    """Tests for the get_fd_interest_bonus() method."""

    def test_no_bonus_for_regular_member(self):
        self.assertEqual(self.member1.get_fd_interest_bonus(), Decimal('0.00'))

    def test_senior_citizen_bonus(self):
        self.member1.is_senior_citizen = True
        self.member1.save()
        self.assertEqual(self.member1.get_fd_interest_bonus(), Decimal('0.50'))

    def test_widow_bonus(self):
        self.member2.is_widow = True
        self.member2.save()
        self.assertEqual(self.member2.get_fd_interest_bonus(), Decimal('0.50'))

    def test_ex_military_bonus(self):
        self.member1.is_ex_military = True
        self.member1.save()
        self.assertEqual(self.member1.get_fd_interest_bonus(), Decimal('0.25'))

    def test_physically_disabled_bonus(self):
        self.member1.is_physically_disabled = True
        self.member1.save()
        self.assertEqual(self.member1.get_fd_interest_bonus(), Decimal('0.25'))

    def test_employee_bonus(self):
        self.member1.is_employee = True
        self.member1.save()
        self.assertEqual(self.member1.get_fd_interest_bonus(), Decimal('0.25'))

    def test_director_bonus(self):
        self.member1.is_director = True
        self.member1.save()
        self.assertEqual(self.member1.get_fd_interest_bonus(), Decimal('0.25'))

    def test_senior_and_military_takes_higher(self):
        """When multiple flags are set, the highest bonus applies."""
        self.member1.is_senior_citizen = True
        self.member1.is_ex_military = True
        self.member1.save()
        self.assertEqual(self.member1.get_fd_interest_bonus(), Decimal('0.50'))

    def test_multiple_small_bonuses_take_max(self):
        """Director + employee + military: all 0.25, result should be 0.25."""
        self.member1.is_director = True
        self.member1.is_employee = True
        self.member1.is_ex_military = True
        self.member1.save()
        self.assertEqual(self.member1.get_fd_interest_bonus(), Decimal('0.25'))
