"""
Cross-module integration tests: exercise the full lifecycle through the real
API end to end. HQ Admin and MR accounts are provisioned directly via the ORM
(`common.factories`); everything else goes through the HTTP API.
"""
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role
from common.factories import HQAdminFactory, MRFactory, SuperAdminFactory
from organizations.models import Headquarters, SubHeadquarters


class FullLifecycleTests(APITestCase):
    PASSWORD = 'pass12345'

    def login_as(self, user):
        response = self.client.post(reverse('auth-login'), {'email': user.email, 'password': self.PASSWORD})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')

    def test_super_admin_to_mr_lifecycle_reflected_everywhere(self):
        # 1. Super Admin creates a Headquarters.
        super_admin = SuperAdminFactory(password=self.PASSWORD)
        self.login_as(super_admin)
        hq_response = self.client.post(reverse('headquarters-list'), {'name': 'Central HQ', 'code': 'CHQ'})
        self.assertEqual(hq_response.status_code, status.HTTP_201_CREATED)
        hq_id = hq_response.data['id']

        # 2. Provision an HQ Admin for that HQ.
        hq = Headquarters.objects.get(pk=hq_id)
        hq_admin = HQAdminFactory(password=self.PASSWORD, headquarters=hq)

        # 3. HQ Admin creates a Sub Headquarters under their own HQ.
        self.login_as(hq_admin)
        sub_hq_response = self.client.post(
            reverse('sub-headquarters-list'), {'headquarters': hq_id, 'name': 'Central Sub A', 'code': 'CHQ-S1'},
        )
        self.assertEqual(sub_hq_response.status_code, status.HTTP_201_CREATED)
        sub_hq_id = sub_hq_response.data['id']

        # 4. Provision an MR under that Sub HQ, then HQ Admin creates a Doctor assigned to them.
        sub_hq = SubHeadquarters.objects.get(pk=sub_hq_id)
        mr = MRFactory(password=self.PASSWORD, headquarters=None, sub_headquarters=sub_hq)
        doctor_response = self.client.post(
            reverse('doctor-list'),
            {'name': 'Dr. Lifecycle', 'sub_headquarters': sub_hq_id, 'assigned_mr': mr.id},
        )
        self.assertEqual(doctor_response.status_code, status.HTTP_201_CREATED)
        doctor_id = doctor_response.data['id']

        # 5. MR creates a Visit for their assigned doctor, then marks it complete.
        self.login_as(mr)
        visit_response = self.client.post(
            reverse('visit-list'), {'doctor': doctor_id, 'visit_date': '2026-06-01'},
        )
        self.assertEqual(visit_response.status_code, status.HTTP_201_CREATED)
        visit_id = visit_response.data['id']

        mark_response = self.client.post(
            reverse('visit-mark-visit', args=[visit_id]), {'remarks': 'First visit done'},
        )
        self.assertEqual(mark_response.status_code, status.HTTP_200_OK)
        self.assertEqual(mark_response.data['status'], 'COMPLETED')

        # 6. Dashboard reflects the new data at every scope in the hierarchy.
        dashboard_response = self.client.get(reverse('dashboard-summary'))
        self.assertEqual(dashboard_response.status_code, status.HTTP_200_OK)
        self.assertEqual(dashboard_response.data['total_doctors'], 1)
        self.assertEqual(dashboard_response.data['completed_visits'], 1)
        self.assertEqual(dashboard_response.data['pending_visits'], 0)

        self.login_as(hq_admin)
        hq_admin_dashboard = self.client.get(reverse('dashboard-summary'))
        self.assertEqual(hq_admin_dashboard.data['total_sub_headquarters'], 1)
        self.assertEqual(hq_admin_dashboard.data['total_doctors'], 1)
        self.assertEqual(hq_admin_dashboard.data['completed_visits'], 1)

        # 7. Super Admin sees it too, and the visits report returns the same visit.
        self.login_as(super_admin)
        super_admin_dashboard = self.client.get(reverse('dashboard-summary'))
        self.assertEqual(super_admin_dashboard.data['total_headquarters'], 1)
        self.assertEqual(super_admin_dashboard.data['completed_visits'], 1)

        report_response = self.client.get(reverse('report-visits'), {'status': 'COMPLETED'})
        self.assertEqual(report_response.status_code, status.HTTP_200_OK)
        self.assertEqual(report_response.data['count'], 1)
        self.assertEqual(report_response.data['results'][0]['id'], visit_id)

        # Sanity: the MR who did the work is a real MR under the hierarchy we built.
        self.assertEqual(mr.role, Role.MR)
        self.assertEqual(mr.sub_headquarters_id, sub_hq_id)
