from datetime import date, timedelta

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role, User
from doctors.models import Doctor
from organizations.models import Headquarters, SubHeadquarters
from visits.models import Visit, VisitStatus


class DashboardSummaryTests(APITestCase):
    PASSWORD = 'pass12345'

    def setUp(self):
        self.hq1 = Headquarters.objects.create(name='North HQ', code='NHQ')
        self.hq2 = Headquarters.objects.create(name='South HQ', code='SHQ')
        self.hq1_sub = SubHeadquarters.objects.create(headquarters=self.hq1, name='North Sub A', code='NHQ-S1')

        self.super_admin = User.objects.create_superuser(email='super@example.com', password=self.PASSWORD)
        self.hq1_admin = User.objects.create_user(
            email='hq1admin@example.com', password=self.PASSWORD, role=Role.HQ_ADMIN, headquarters=self.hq1,
        )
        self.hq1_staff = User.objects.create_user(
            email='hq1staff@example.com', password=self.PASSWORD, role=Role.HQ_STAFF, headquarters=self.hq1,
        )
        self.hq1_sub_staff = User.objects.create_user(
            email='hq1substaff@example.com', password=self.PASSWORD,
            role=Role.SUB_HQ_STAFF, sub_headquarters=self.hq1_sub,
        )
        self.mr_hq1 = User.objects.create_user(
            email='mrhq1@example.com', password=self.PASSWORD, role=Role.MR, headquarters=self.hq1,
        )
        self.mr_hq1_sub = User.objects.create_user(
            email='mrhq1sub@example.com', password=self.PASSWORD, role=Role.MR, sub_headquarters=self.hq1_sub,
        )
        self.mr_hq2 = User.objects.create_user(
            email='mrhq2@example.com', password=self.PASSWORD, role=Role.MR, headquarters=self.hq2,
        )

        self.doc_hq1 = Doctor.objects.create(name='Dr. Hq1', headquarters=self.hq1, assigned_mr=self.mr_hq1)
        self.doc_hq1_sub = Doctor.objects.create(name='Dr. Hq1Sub', sub_headquarters=self.hq1_sub, assigned_mr=self.mr_hq1_sub)
        self.doc_hq2 = Doctor.objects.create(name='Dr. Hq2', headquarters=self.hq2, assigned_mr=self.mr_hq2)

        today = date.today()
        yesterday = today - timedelta(days=1)

        # Today's visits, split PENDING/COMPLETED, across hq1 (direct), hq1_sub, and hq2.
        Visit.objects.create(doctor=self.doc_hq1, mr=self.mr_hq1, visit_date=today, status=VisitStatus.PENDING)
        Visit.objects.create(doctor=self.doc_hq1, mr=self.mr_hq1, visit_date=today, status=VisitStatus.COMPLETED)
        Visit.objects.create(doctor=self.doc_hq1_sub, mr=self.mr_hq1_sub, visit_date=today, status=VisitStatus.PENDING)
        Visit.objects.create(doctor=self.doc_hq2, mr=self.mr_hq2, visit_date=yesterday, status=VisitStatus.COMPLETED)
        Visit.objects.create(doctor=self.doc_hq2, mr=self.mr_hq2, visit_date=today, status=VisitStatus.PENDING)

    def login_as(self, user):
        response = self.client.post(reverse('auth-login'), {'email': user.email, 'password': self.PASSWORD})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')

    def test_super_admin_sees_global_counts(self):
        self.login_as(self.super_admin)
        response = self.client.get(reverse('dashboard-summary'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {
            'total_headquarters': 2,
            'total_sub_headquarters': 1,
            'total_doctors': 3,
            'total_mrs': 3,
            'todays_visits': 4,
            'completed_visits': 2,
            'pending_visits': 3,
        })

    def test_hq_admin_sees_own_hq_plus_sub_hq_counts(self):
        self.login_as(self.hq1_admin)
        response = self.client.get(reverse('dashboard-summary'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {
            'total_headquarters': 1,
            'total_sub_headquarters': 1,
            'total_doctors': 2,
            'total_mrs': 2,
            'todays_visits': 3,
            'completed_visits': 1,
            'pending_visits': 2,
        })

    def test_hq_staff_sees_only_own_hq_direct_counts(self):
        self.login_as(self.hq1_staff)
        response = self.client.get(reverse('dashboard-summary'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {
            'total_headquarters': 1,
            'total_sub_headquarters': 1,
            'total_doctors': 1,
            'total_mrs': 1,
            'todays_visits': 2,
            'completed_visits': 1,
            'pending_visits': 1,
        })

    def test_sub_hq_staff_sees_only_own_sub_hq_counts(self):
        self.login_as(self.hq1_sub_staff)
        response = self.client.get(reverse('dashboard-summary'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {
            'total_headquarters': 0,
            'total_sub_headquarters': 1,
            'total_doctors': 1,
            'total_mrs': 1,
            'todays_visits': 1,
            'completed_visits': 0,
            'pending_visits': 1,
        })

    def test_mr_sees_self_scoped_counts(self):
        self.login_as(self.mr_hq1)
        response = self.client.get(reverse('dashboard-summary'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {
            'total_headquarters': 0,
            'total_sub_headquarters': 0,
            'total_doctors': 1,
            'total_mrs': 1,
            'todays_visits': 2,
            'completed_visits': 1,
            'pending_visits': 1,
        })

    def test_unauthenticated_request_rejected(self):
        response = self.client.get(reverse('dashboard-summary'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
