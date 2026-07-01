from datetime import date

from django.test import TestCase

from accounts.models import Role, User
from doctors.models import Doctor
from organizations.models import Headquarters
from visits.models import Visit, VisitStatus


class VisitModelTests(TestCase):
    def setUp(self):
        self.hq = Headquarters.objects.create(name='North HQ', code='NHQ')
        self.mr = User.objects.create_user(email='mr@example.com', password='pass12345', role=Role.MR, headquarters=self.hq)
        self.doctor = Doctor.objects.create(name='Dr. A', headquarters=self.hq)

    def test_visit_defaults_to_pending_status(self):
        visit = Visit.objects.create(doctor=self.doctor, mr=self.mr, visit_date=date.today())
        self.assertEqual(visit.status, VisitStatus.PENDING)
        self.assertIsNone(visit.check_in_time)

    def test_str_includes_doctor_date_and_status(self):
        visit = Visit.objects.create(doctor=self.doctor, mr=self.mr, visit_date=date(2026, 1, 1))
        self.assertIn('Dr. A', str(visit))
        self.assertIn('2026-01-01', str(visit))
        self.assertIn('PENDING', str(visit))

    def test_deleting_doctor_cascades_to_visits(self):
        visit = Visit.objects.create(doctor=self.doctor, mr=self.mr, visit_date=date.today())
        self.doctor.delete()
        self.assertFalse(Visit.objects.filter(pk=visit.pk).exists())

    def test_deleting_mr_cascades_to_visits(self):
        visit = Visit.objects.create(doctor=self.doctor, mr=self.mr, visit_date=date.today())
        self.mr.delete()
        self.assertFalse(Visit.objects.filter(pk=visit.pk).exists())
