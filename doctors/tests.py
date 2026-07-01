from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.models import Role, User
from doctors.models import Doctor
from organizations.models import Headquarters, SubHeadquarters


class DoctorModelTests(TestCase):
    def setUp(self):
        self.hq = Headquarters.objects.create(name='North HQ', code='NHQ')
        self.sub_hq = SubHeadquarters.objects.create(headquarters=self.hq, name='North Sub', code='NHQ-S1')
        self.mr = User.objects.create_user(email='mr@example.com', password='pass12345', role=Role.MR, headquarters=self.hq)
        self.non_mr = User.objects.create_user(email='staff@example.com', password='pass12345', role=Role.HQ_STAFF, headquarters=self.hq)

    def test_doctor_scoped_to_headquarters_is_valid(self):
        doctor = Doctor(name='Dr. A', headquarters=self.hq)
        doctor.full_clean()  # should not raise

    def test_doctor_scoped_to_sub_headquarters_is_valid(self):
        doctor = Doctor(name='Dr. B', sub_headquarters=self.sub_hq)
        doctor.full_clean()  # should not raise

    def test_doctor_requires_exactly_one_parent_neither_set(self):
        doctor = Doctor(name='Dr. C')
        with self.assertRaises(ValidationError):
            doctor.full_clean()

    def test_doctor_requires_exactly_one_parent_both_set(self):
        doctor = Doctor(name='Dr. D', headquarters=self.hq, sub_headquarters=self.sub_hq)
        with self.assertRaises(ValidationError):
            doctor.full_clean()

    def test_doctor_check_constraint_enforced_at_db_level(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Doctor.objects.create(name='Dr. E')

    def test_assigned_mr_must_have_mr_role(self):
        doctor = Doctor(name='Dr. F', headquarters=self.hq, assigned_mr=self.non_mr)
        with self.assertRaises(ValidationError):
            doctor.full_clean()

    def test_assigned_mr_with_mr_role_is_valid(self):
        doctor = Doctor(name='Dr. G', headquarters=self.hq, assigned_mr=self.mr)
        doctor.full_clean()  # should not raise
