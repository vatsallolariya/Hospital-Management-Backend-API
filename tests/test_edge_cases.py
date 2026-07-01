"""
Edge cases: invalid filter values, empty result sets, pagination
boundaries, and expired or malformed JWTs.
"""
from datetime import timedelta

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import Role
from common.factories import DoctorFactory, HeadquartersFactory, MRFactory, SuperAdminFactory, VisitFactory


class EdgeCaseBase(APITestCase):
    PASSWORD = 'pass12345'

    def setUp(self):
        self.hq = HeadquartersFactory()
        self.super_admin = SuperAdminFactory(password=self.PASSWORD)
        self.mr = MRFactory(password=self.PASSWORD, headquarters=self.hq)
        self.doctor = DoctorFactory(headquarters=self.hq, assigned_mr=self.mr)
        self.visit = VisitFactory(doctor=self.doctor, mr=self.mr)

    def login_as(self, user):
        response = self.client.post(reverse('auth-login'), {'email': user.email, 'password': self.PASSWORD})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')


class InvalidFilterTests(EdgeCaseBase):
    """Invalid filter values return a 400, not an empty result or a 500."""
    def test_invalid_visit_status_filter_returns_400(self):
        self.login_as(self.super_admin)
        response = self.client.get(reverse('visit-list'), {'status': 'BOGUS'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_report_headquarters_filter_returns_400(self):
        self.login_as(self.super_admin)
        response = self.client.get(reverse('report-visits'), {'headquarters': 'not-an-int'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_visit_date_filter_returns_400(self):
        self.login_as(self.super_admin)
        response = self.client.get(reverse('visit-list'), {'date': 'not-a-date'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class EmptyResultTests(EdgeCaseBase):
    def test_search_with_no_matches_returns_200_and_zero_count(self):
        self.login_as(self.super_admin)
        response = self.client.get(reverse('doctor-list'), {'search': 'no-such-doctor-name-xyz'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)
        self.assertEqual(response.data['results'], [])

    def test_filter_with_no_matches_returns_200_and_zero_count(self):
        self.login_as(self.super_admin)
        response = self.client.get(reverse('visit-list'), {'status': 'CANCELLED'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)


class PaginationBoundaryTests(EdgeCaseBase):
    def test_page_beyond_last_page_returns_404(self):
        self.login_as(self.super_admin)
        response = self.client.get(reverse('doctor-list'), {'page': 9999})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_page_size_is_clamped_to_max(self):
        self.login_as(self.super_admin)
        response = self.client.get(reverse('doctor-list'), {'page_size': 1000})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(response.data['results']), 100)

    def test_non_numeric_page_size_falls_back_to_default(self):
        self.login_as(self.super_admin)
        response = self.client.get(reverse('doctor-list'), {'page_size': 'abc'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ExpiredTokenTests(EdgeCaseBase):
    def _expired_token_for(self, user):
        token = AccessToken.for_user(user)
        token.set_exp(lifetime=timedelta(seconds=-1))
        return str(token)

    def test_expired_token_rejected_on_dashboard(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self._expired_token_for(self.super_admin)}')
        response = self.client.get(reverse('dashboard-summary'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_expired_token_rejected_on_reports(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self._expired_token_for(self.super_admin)}')
        response = self.client.get(reverse('report-visits'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_expired_token_rejected_on_doctors(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self._expired_token_for(self.super_admin)}')
        response = self.client.get(reverse('doctor-list'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_expired_token_rejected_on_visits(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self._expired_token_for(self.super_admin)}')
        response = self.client.get(reverse('visit-list'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_malformed_token_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer not-a-real-token')
        response = self.client.get(reverse('dashboard-summary'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_missing_token_rejected(self):
        response = self.client.get(reverse('doctor-list'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
