"""
Full RBAC permission-matrix sweep: every role x every resource x
every verb. Existing
per-app tests.py files already spot-check individual RBAC rules; this module
is the single, exhaustive, table-driven cross-check — a regression test for
the permission *gate* (allowed vs 403), not the queryset-scoping correctness
already covered elsewhere.
"""
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role
from common.factories import (
    DoctorFactory, HeadquartersFactory, HQAdminFactory, HQStaffFactory,
    MRFactory, SubHeadquartersFactory, SubHQStaffFactory, SuperAdminFactory,
    VisitFactory,
)

ALL_ROLES = [Role.SUPER_ADMIN, Role.HQ_ADMIN, Role.HQ_STAFF, Role.SUB_HQ_STAFF, Role.MR]


class PermissionMatrixBase(APITestCase):
    PASSWORD = 'pass12345'

    def setUp(self):
        self.hq = HeadquartersFactory()
        self.sub_hq = SubHeadquartersFactory(headquarters=self.hq)

        self.users = {
            Role.SUPER_ADMIN: SuperAdminFactory(password=self.PASSWORD),
            Role.HQ_ADMIN: HQAdminFactory(password=self.PASSWORD, headquarters=self.hq),
            Role.HQ_STAFF: HQStaffFactory(password=self.PASSWORD, headquarters=self.hq),
            Role.SUB_HQ_STAFF: SubHQStaffFactory(password=self.PASSWORD, sub_headquarters=self.sub_hq),
            Role.MR: MRFactory(password=self.PASSWORD, headquarters=self.hq),
        }

        # A doctor/visit directly under the HQ (owned by SA/HQ Admin/HQ Staff/MR)...
        self.doctor = DoctorFactory(headquarters=self.hq, sub_headquarters=None, assigned_mr=self.users[Role.MR])
        self.visit = VisitFactory(doctor=self.doctor, mr=self.users[Role.MR])

        # ...and a separate doctor/visit under the Sub HQ (owned by Sub HQ Staff),
        # since Sub HQ Staff's scope is the Sub HQ, not the HQ directly.
        self.sub_mr = MRFactory(password=self.PASSWORD, headquarters=None, sub_headquarters=self.sub_hq)
        self.sub_doctor = DoctorFactory(headquarters=None, sub_headquarters=self.sub_hq, assigned_mr=self.sub_mr)
        self.sub_visit = VisitFactory(doctor=self.sub_doctor, mr=self.sub_mr)

    def login_as(self, role):
        user = self.users[role]
        response = self.client.post(reverse('auth-login'), {'email': user.email, 'password': self.PASSWORD})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')

    def assert_role_status(self, role, method, url, allowed, data=None):
        self.login_as(role)
        response = getattr(self.client, method)(url, data or {}, format='json')
        self.client.credentials()
        if allowed:
            self.assertIn(
                response.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED, status.HTTP_204_NO_CONTENT),
                f'{role} {method.upper()} {url} expected to be allowed, got {response.status_code}: {response.data if hasattr(response, "data") else response.content}',
            )
        else:
            self.assertEqual(
                response.status_code, status.HTTP_403_FORBIDDEN,
                f'{role} {method.upper()} {url} expected 403, got {response.status_code}',
            )


class HeadquartersMatrixTests(PermissionMatrixBase):
    READ_ROLES = {Role.SUPER_ADMIN, Role.HQ_ADMIN, Role.HQ_STAFF}
    WRITE_ROLES = {Role.SUPER_ADMIN}

    def test_list(self):
        for role in ALL_ROLES:
            with self.subTest(role=role):
                self.assert_role_status(role, 'get', reverse('headquarters-list'), role in self.READ_ROLES)

    def test_retrieve(self):
        url = reverse('headquarters-detail', args=[self.hq.id])
        for role in ALL_ROLES:
            with self.subTest(role=role):
                self.assert_role_status(role, 'get', url, role in self.READ_ROLES)

    def test_create(self):
        for role in ALL_ROLES:
            with self.subTest(role=role):
                payload = {'name': f'New HQ {role}', 'code': f'NEW-{role}'}
                self.assert_role_status(role, 'post', reverse('headquarters-list'), role in self.WRITE_ROLES, payload)

    def test_update(self):
        url = reverse('headquarters-detail', args=[self.hq.id])
        for role in ALL_ROLES:
            with self.subTest(role=role):
                self.assert_role_status(role, 'patch', url, role in self.WRITE_ROLES, {'city': 'Metropolis'})

    def test_delete(self):
        for role in ALL_ROLES:
            with self.subTest(role=role):
                target = HeadquartersFactory() if role in self.WRITE_ROLES else self.hq
                url = reverse('headquarters-detail', args=[target.id])
                self.assert_role_status(role, 'delete', url, role in self.WRITE_ROLES)


class SubHeadquartersMatrixTests(PermissionMatrixBase):
    READ_ROLES = {Role.SUPER_ADMIN, Role.HQ_ADMIN, Role.HQ_STAFF, Role.SUB_HQ_STAFF}
    WRITE_ROLES = {Role.SUPER_ADMIN, Role.HQ_ADMIN}

    def test_list(self):
        for role in ALL_ROLES:
            with self.subTest(role=role):
                self.assert_role_status(role, 'get', reverse('sub-headquarters-list'), role in self.READ_ROLES)

    def test_retrieve(self):
        url = reverse('sub-headquarters-detail', args=[self.sub_hq.id])
        for role in ALL_ROLES:
            with self.subTest(role=role):
                self.assert_role_status(role, 'get', url, role in self.READ_ROLES)

    def test_create(self):
        for role in ALL_ROLES:
            with self.subTest(role=role):
                payload = {'headquarters': self.hq.id, 'name': f'New Sub {role}', 'code': f'NEW-{role}'}
                self.assert_role_status(role, 'post', reverse('sub-headquarters-list'), role in self.WRITE_ROLES, payload)

    def test_update(self):
        url = reverse('sub-headquarters-detail', args=[self.sub_hq.id])
        for role in ALL_ROLES:
            with self.subTest(role=role):
                self.assert_role_status(role, 'patch', url, role in self.WRITE_ROLES, {'address': '123 Main St'})

    def test_delete(self):
        for role in ALL_ROLES:
            with self.subTest(role=role):
                target = SubHeadquartersFactory(headquarters=self.hq) if role in self.WRITE_ROLES else self.sub_hq
                url = reverse('sub-headquarters-detail', args=[target.id])
                self.assert_role_status(role, 'delete', url, role in self.WRITE_ROLES)


class DoctorMatrixTests(PermissionMatrixBase):
    READ_ROLES = set(ALL_ROLES)
    WRITE_ROLES = {Role.SUPER_ADMIN, Role.HQ_ADMIN, Role.HQ_STAFF, Role.SUB_HQ_STAFF}

    def target_for(self, role):
        return self.sub_doctor if role == Role.SUB_HQ_STAFF else self.doctor

    def payload_for(self, role):
        if role == Role.SUB_HQ_STAFF:
            return {'name': f'Dr {role}', 'sub_headquarters': self.sub_hq.id}
        return {'name': f'Dr {role}', 'headquarters': self.hq.id}

    def test_list(self):
        for role in ALL_ROLES:
            with self.subTest(role=role):
                self.assert_role_status(role, 'get', reverse('doctor-list'), role in self.READ_ROLES)

    def test_retrieve(self):
        for role in ALL_ROLES:
            with self.subTest(role=role):
                url = reverse('doctor-detail', args=[self.target_for(role).id])
                self.assert_role_status(role, 'get', url, role in self.READ_ROLES)

    def test_create(self):
        for role in ALL_ROLES:
            with self.subTest(role=role):
                self.assert_role_status(
                    role, 'post', reverse('doctor-list'), role in self.WRITE_ROLES, self.payload_for(role),
                )

    def test_update(self):
        for role in ALL_ROLES:
            with self.subTest(role=role):
                url = reverse('doctor-detail', args=[self.target_for(role).id])
                self.assert_role_status(role, 'patch', url, role in self.WRITE_ROLES, {'specialization': 'Cardiology'})

    def test_delete(self):
        for role in ALL_ROLES:
            with self.subTest(role=role):
                if role in self.WRITE_ROLES:
                    target = (
                        DoctorFactory(headquarters=None, sub_headquarters=self.sub_hq) if role == Role.SUB_HQ_STAFF
                        else DoctorFactory(headquarters=self.hq)
                    )
                else:
                    target = self.doctor
                url = reverse('doctor-detail', args=[target.id])
                self.assert_role_status(role, 'delete', url, role in self.WRITE_ROLES)


class VisitMatrixTests(PermissionMatrixBase):
    READ_ROLES = set(ALL_ROLES)
    CREATE_ROLES = {Role.SUPER_ADMIN, Role.HQ_STAFF, Role.SUB_HQ_STAFF, Role.MR}
    UPDATE_ROLES = set(ALL_ROLES)
    DELETE_ROLES = {Role.SUPER_ADMIN, Role.HQ_STAFF, Role.SUB_HQ_STAFF}

    def target_for(self, role):
        return self.sub_visit if role == Role.SUB_HQ_STAFF else self.visit

    def payload_for(self, role):
        if role == Role.MR:
            return {'doctor': self.doctor.id, 'visit_date': '2026-03-01'}
        if role == Role.SUB_HQ_STAFF:
            return {'doctor': self.sub_doctor.id, 'mr': self.sub_mr.id, 'visit_date': '2026-03-01'}
        return {'doctor': self.doctor.id, 'mr': self.users[Role.MR].id, 'visit_date': '2026-03-01'}

    def test_list(self):
        for role in ALL_ROLES:
            with self.subTest(role=role):
                self.assert_role_status(role, 'get', reverse('visit-list'), role in self.READ_ROLES)

    def test_retrieve(self):
        for role in ALL_ROLES:
            with self.subTest(role=role):
                url = reverse('visit-detail', args=[self.target_for(role).id])
                self.assert_role_status(role, 'get', url, role in self.READ_ROLES)

    def test_create(self):
        for role in ALL_ROLES:
            with self.subTest(role=role):
                self.assert_role_status(
                    role, 'post', reverse('visit-list'), role in self.CREATE_ROLES, self.payload_for(role),
                )

    def test_update(self):
        for role in ALL_ROLES:
            with self.subTest(role=role):
                url = reverse('visit-detail', args=[self.target_for(role).id])
                self.assert_role_status(role, 'patch', url, role in self.UPDATE_ROLES, {'remarks': 'Updated'})

    def test_delete(self):
        for role in ALL_ROLES:
            with self.subTest(role=role):
                if role in self.DELETE_ROLES:
                    target = (
                        VisitFactory(doctor=self.sub_doctor, mr=self.sub_mr) if role == Role.SUB_HQ_STAFF
                        else VisitFactory(doctor=self.doctor, mr=self.users[Role.MR])
                    )
                else:
                    target = self.visit
                url = reverse('visit-detail', args=[target.id])
                self.assert_role_status(role, 'delete', url, role in self.DELETE_ROLES)


class DashboardReportsMatrixTests(PermissionMatrixBase):
    """Dashboard/Reports are read-only, IsAuthenticated-only — every role gets 200 (scoped values)."""

    def test_dashboard_summary_allowed_for_every_role(self):
        for role in ALL_ROLES:
            with self.subTest(role=role):
                self.assert_role_status(role, 'get', reverse('dashboard-summary'), allowed=True)

    def test_reports_visits_allowed_for_every_role(self):
        for role in ALL_ROLES:
            with self.subTest(role=role):
                self.assert_role_status(role, 'get', reverse('report-visits'), allowed=True)
