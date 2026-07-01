from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

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


class DoctorAPITestCase(APITestCase):
    """Shared fixtures for Doctor CRUD + RBAC tests."""

    PASSWORD = 'pass12345'

    def setUp(self):
        self.hq1 = Headquarters.objects.create(name='North HQ', code='NHQ')
        self.hq2 = Headquarters.objects.create(name='South HQ', code='SHQ')
        self.hq1_sub = SubHeadquarters.objects.create(headquarters=self.hq1, name='North Sub A', code='NHQ-S1')
        self.hq2_sub = SubHeadquarters.objects.create(headquarters=self.hq2, name='South Sub A', code='SHQ-S1')

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
        self.mr_sub1 = User.objects.create_user(
            email='mrsub1@example.com', password=self.PASSWORD, role=Role.MR, sub_headquarters=self.hq1_sub,
        )
        self.mr_hq2 = User.objects.create_user(
            email='mrhq2@example.com', password=self.PASSWORD, role=Role.MR, headquarters=self.hq2,
        )

        self.doc_hq1 = Doctor.objects.create(name='Dr. Hq1', headquarters=self.hq1, assigned_mr=self.mr_hq1)
        self.doc_hq1_sub = Doctor.objects.create(name='Dr. Hq1Sub', sub_headquarters=self.hq1_sub, assigned_mr=self.mr_sub1)
        self.doc_hq2 = Doctor.objects.create(name='Dr. Hq2', headquarters=self.hq2)
        self.doc_hq2_sub = Doctor.objects.create(name='Dr. Hq2Sub', sub_headquarters=self.hq2_sub)

    def login_as(self, user):
        response = self.client.post(reverse('auth-login'), {'email': user.email, 'password': self.PASSWORD})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')


class DoctorListRetrieveTests(DoctorAPITestCase):
    def test_super_admin_sees_all_doctors(self):
        self.login_as(self.super_admin)
        response = self.client.get(reverse('doctor-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 4)

    def test_hq_admin_sees_own_hq_and_own_sub_hq_doctors(self):
        self.login_as(self.hq1_admin)
        response = self.client.get(reverse('doctor-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {row['id'] for row in response.data['results']}
        self.assertEqual(ids, {self.doc_hq1.id, self.doc_hq1_sub.id})

    def test_hq_admin_cannot_retrieve_other_hq_doctor(self):
        self.login_as(self.hq1_admin)
        response = self.client.get(reverse('doctor-detail', args=[self.doc_hq2.id]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_hq_staff_sees_only_doctors_directly_under_own_hq(self):
        self.login_as(self.hq1_staff)
        response = self.client.get(reverse('doctor-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], self.doc_hq1.id)

    def test_sub_hq_staff_sees_only_own_sub_hq_doctors(self):
        self.login_as(self.hq1_sub_staff)
        response = self.client.get(reverse('doctor-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], self.doc_hq1_sub.id)

    def test_mr_sees_only_own_assigned_doctors(self):
        self.login_as(self.mr_hq1)
        response = self.client.get(reverse('doctor-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], self.doc_hq1.id)

    def test_search_filters_by_name(self):
        self.login_as(self.super_admin)
        response = self.client.get(reverse('doctor-list'), {'search': 'Hq2Sub'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], self.doc_hq2_sub.id)

    def test_filter_by_headquarters(self):
        self.login_as(self.super_admin)
        response = self.client.get(reverse('doctor-list'), {'headquarters': self.hq2.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], self.doc_hq2.id)

    def test_ordering_by_name_descending(self):
        self.login_as(self.super_admin)
        response = self.client.get(reverse('doctor-list'), {'ordering': '-name'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [row['name'] for row in response.data['results']]
        self.assertEqual(names, sorted(names, reverse=True))


class DoctorCreateUpdateDeleteTests(DoctorAPITestCase):
    def test_super_admin_can_create_under_headquarters(self):
        self.login_as(self.super_admin)
        response = self.client.post(reverse('doctor-list'), {'name': 'Dr. New', 'headquarters': self.hq2.id})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['created_by'], self.super_admin.id)

    def test_super_admin_can_create_under_sub_headquarters(self):
        self.login_as(self.super_admin)
        response = self.client.post(reverse('doctor-list'), {'name': 'Dr. New', 'sub_headquarters': self.hq2_sub.id})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_creating_with_both_hq_and_sub_hq_rejected(self):
        self.login_as(self.super_admin)
        response = self.client.post(
            reverse('doctor-list'),
            {'name': 'Dr. New', 'headquarters': self.hq1.id, 'sub_headquarters': self.hq1_sub.id},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_creating_with_neither_hq_nor_sub_hq_rejected(self):
        self.login_as(self.super_admin)
        response = self.client.post(reverse('doctor-list'), {'name': 'Dr. New'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_hq_admin_can_create_under_own_hq(self):
        self.login_as(self.hq1_admin)
        response = self.client.post(reverse('doctor-list'), {'name': 'Dr. New', 'headquarters': self.hq1.id})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_hq_admin_can_create_under_own_sub_hq(self):
        self.login_as(self.hq1_admin)
        response = self.client.post(reverse('doctor-list'), {'name': 'Dr. New', 'sub_headquarters': self.hq1_sub.id})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_hq_admin_cannot_create_under_other_hq(self):
        self.login_as(self.hq1_admin)
        response = self.client.post(reverse('doctor-list'), {'name': 'Dr. Sneaky', 'headquarters': self.hq2.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_hq_staff_cannot_create_under_own_sub_hq(self):
        self.login_as(self.hq1_staff)
        response = self.client.post(reverse('doctor-list'), {'name': 'Dr. Sneaky', 'sub_headquarters': self.hq1_sub.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_sub_hq_staff_can_create_under_own_sub_hq(self):
        self.login_as(self.hq1_sub_staff)
        response = self.client.post(reverse('doctor-list'), {'name': 'Dr. New', 'sub_headquarters': self.hq1_sub.id})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_sub_hq_staff_cannot_create_under_headquarters(self):
        self.login_as(self.hq1_sub_staff)
        response = self.client.post(reverse('doctor-list'), {'name': 'Dr. Sneaky', 'headquarters': self.hq1.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_mr_cannot_create_doctor(self):
        self.login_as(self.mr_hq1)
        response = self.client.post(reverse('doctor-list'), {'name': 'Dr. Sneaky', 'headquarters': self.hq1.id})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_mr_cannot_update_doctor(self):
        self.login_as(self.mr_hq1)
        response = self.client.patch(reverse('doctor-detail', args=[self.doc_hq1.id]), {'phone': '555-0100'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_hq_admin_can_delete_own_hq_doctor(self):
        self.login_as(self.hq1_admin)
        response = self.client.delete(reverse('doctor-detail', args=[self.doc_hq1.id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_assigned_mr_must_have_mr_role(self):
        self.login_as(self.super_admin)
        response = self.client.post(
            reverse('doctor-list'),
            {'name': 'Dr. New', 'headquarters': self.hq1.id, 'assigned_mr': self.hq1_staff.id},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_assigned_mr_must_belong_to_same_headquarters(self):
        self.login_as(self.super_admin)
        response = self.client.post(
            reverse('doctor-list'),
            {'name': 'Dr. New', 'headquarters': self.hq1.id, 'assigned_mr': self.mr_hq2.id},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_assigned_mr_must_belong_to_same_sub_headquarters(self):
        self.login_as(self.super_admin)
        response = self.client.post(
            reverse('doctor-list'),
            {'name': 'Dr. New', 'sub_headquarters': self.hq1_sub.id, 'assigned_mr': self.mr_hq2.id},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reassigning_to_matching_mr_succeeds(self):
        self.login_as(self.super_admin)
        response = self.client.patch(
            reverse('doctor-detail', args=[self.doc_hq2.id]), {'assigned_mr': self.mr_hq2.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['assigned_mr'], self.mr_hq2.id)
