from datetime import date

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role, User
from doctors.models import Doctor
from organizations.models import Headquarters, SubHeadquarters
from visits.models import Visit, VisitStatus


class VisitReportTestCase(APITestCase):
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

        self.v1 = Visit.objects.create(doctor=self.doc_hq1, mr=self.mr_hq1, visit_date=date(2026, 1, 1), status=VisitStatus.PENDING)
        self.v2 = Visit.objects.create(doctor=self.doc_hq1, mr=self.mr_hq1, visit_date=date(2026, 1, 5), status=VisitStatus.COMPLETED)
        self.v3 = Visit.objects.create(doctor=self.doc_hq1_sub, mr=self.mr_hq1_sub, visit_date=date(2026, 1, 10), status=VisitStatus.PENDING)
        self.v4 = Visit.objects.create(doctor=self.doc_hq2, mr=self.mr_hq2, visit_date=date(2026, 1, 15), status=VisitStatus.CANCELLED)
        self.v5 = Visit.objects.create(doctor=self.doc_hq2, mr=self.mr_hq2, visit_date=date(2026, 1, 20), status=VisitStatus.COMPLETED)

    def login_as(self, user):
        response = self.client.post(reverse('auth-login'), {'email': user.email, 'password': self.PASSWORD})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')

    def ids(self, response):
        return {row['id'] for row in response.data['results']}


class VisitReportScopingTests(VisitReportTestCase):
    def test_super_admin_sees_all_visits(self):
        self.login_as(self.super_admin)
        response = self.client.get(reverse('report-visits'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 5)

    def test_hq_admin_sees_own_hq_plus_sub_hq_visits(self):
        self.login_as(self.hq1_admin)
        response = self.client.get(reverse('report-visits'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.ids(response), {self.v1.id, self.v2.id, self.v3.id})

    def test_hq_staff_sees_only_direct_hq_visits(self):
        self.login_as(self.hq1_staff)
        response = self.client.get(reverse('report-visits'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.ids(response), {self.v1.id, self.v2.id})

    def test_sub_hq_staff_sees_only_own_sub_hq_visits(self):
        self.login_as(self.hq1_sub_staff)
        response = self.client.get(reverse('report-visits'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.ids(response), {self.v3.id})

    def test_mr_sees_only_own_visits(self):
        self.login_as(self.mr_hq1)
        response = self.client.get(reverse('report-visits'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.ids(response), {self.v1.id, self.v2.id})


class VisitReportFilterTests(VisitReportTestCase):
    def test_filter_by_date_range(self):
        self.login_as(self.super_admin)
        response = self.client.get(reverse('report-visits'), {'start_date': '2026-01-05', 'end_date': '2026-01-15'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.ids(response), {self.v2.id, self.v3.id, self.v4.id})

    def test_filter_by_status(self):
        self.login_as(self.super_admin)
        response = self.client.get(reverse('report-visits'), {'status': 'CANCELLED'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.ids(response), {self.v4.id})

    def test_filter_by_headquarters(self):
        self.login_as(self.super_admin)
        response = self.client.get(reverse('report-visits'), {'headquarters': self.hq2.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.ids(response), {self.v4.id, self.v5.id})

    def test_filter_by_headquarters_includes_its_sub_headquarters(self):
        self.login_as(self.super_admin)
        response = self.client.get(reverse('report-visits'), {'headquarters': self.hq1.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.ids(response), {self.v1.id, self.v2.id, self.v3.id})

    def test_filter_by_sub_headquarters(self):
        self.login_as(self.super_admin)
        response = self.client.get(reverse('report-visits'), {'sub_headquarters': self.hq1_sub.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.ids(response), {self.v3.id})

    def test_filter_by_doctor(self):
        self.login_as(self.super_admin)
        response = self.client.get(reverse('report-visits'), {'doctor': self.doc_hq2.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.ids(response), {self.v4.id, self.v5.id})

    def test_filter_by_mr(self):
        self.login_as(self.super_admin)
        response = self.client.get(reverse('report-visits'), {'mr': self.mr_hq1.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.ids(response), {self.v1.id, self.v2.id})

    def test_search_by_doctor_name(self):
        self.login_as(self.super_admin)
        response = self.client.get(reverse('report-visits'), {'search': 'Hq2'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.ids(response), {self.v4.id, self.v5.id})

    def test_ordering_by_visit_date_ascending(self):
        self.login_as(self.super_admin)
        response = self.client.get(reverse('report-visits'), {'ordering': 'visit_date'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        dates = [row['visit_date'] for row in response.data['results']]
        self.assertEqual(dates, sorted(dates))

    def test_hq_staff_cannot_see_other_hq_via_headquarters_filter(self):
        self.login_as(self.hq1_staff)
        response = self.client.get(reverse('report-visits'), {'headquarters': self.hq2.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)

    def test_unauthenticated_request_rejected(self):
        response = self.client.get(reverse('report-visits'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
