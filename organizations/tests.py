from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role, User
from organizations.models import Headquarters, SubHeadquarters


class HeadquartersModelTests(TestCase):
    def test_str_includes_name_and_code(self):
        hq = Headquarters.objects.create(name='North HQ', code='NHQ')
        self.assertEqual(str(hq), 'North HQ (NHQ)')

    def test_name_must_be_unique(self):
        Headquarters.objects.create(name='North HQ', code='NHQ')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Headquarters.objects.create(name='North HQ', code='NHQ2')

    def test_code_must_be_unique(self):
        Headquarters.objects.create(name='North HQ', code='NHQ')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Headquarters.objects.create(name='Other HQ', code='NHQ')


class SubHeadquartersModelTests(TestCase):
    def setUp(self):
        self.hq = Headquarters.objects.create(name='North HQ', code='NHQ')

    def test_code_unique_per_headquarters_only(self):
        SubHeadquarters.objects.create(headquarters=self.hq, name='Sub A', code='S1')
        other_hq = Headquarters.objects.create(name='South HQ', code='SHQ')
        # Same code under a different HQ is fine.
        SubHeadquarters.objects.create(headquarters=other_hq, name='Sub A', code='S1')

    def test_duplicate_code_within_same_headquarters_rejected(self):
        SubHeadquarters.objects.create(headquarters=self.hq, name='Sub A', code='S1')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SubHeadquarters.objects.create(headquarters=self.hq, name='Sub B', code='S1')

    def test_deleting_headquarters_cascades_to_sub_headquarters(self):
        sub = SubHeadquarters.objects.create(headquarters=self.hq, name='Sub A', code='S1')
        self.hq.delete()
        self.assertFalse(SubHeadquarters.objects.filter(pk=sub.pk).exists())


class OrganizationsAPITestCase(APITestCase):
    """Shared fixtures for Headquarters/Sub Headquarters CRUD + RBAC tests."""

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
        self.mr = User.objects.create_user(
            email='mr@example.com', password=self.PASSWORD, role=Role.MR, headquarters=self.hq1,
        )

    def login_as(self, user):
        response = self.client.post(reverse('auth-login'), {'email': user.email, 'password': self.PASSWORD})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')


class HeadquartersAPITests(OrganizationsAPITestCase):
    def test_super_admin_sees_all_headquarters(self):
        self.login_as(self.super_admin)
        response = self.client.get(reverse('headquarters-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)

    def test_super_admin_can_create_headquarters(self):
        self.login_as(self.super_admin)
        response = self.client.post(reverse('headquarters-list'), {'name': 'East HQ', 'code': 'EHQ'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['created_by'], self.super_admin.id)

    def test_hq_admin_sees_only_own_headquarters(self):
        self.login_as(self.hq1_admin)
        response = self.client.get(reverse('headquarters-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], self.hq1.id)

    def test_hq_admin_cannot_retrieve_other_headquarters(self):
        self.login_as(self.hq1_admin)
        response = self.client.get(reverse('headquarters-detail', args=[self.hq2.id]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_hq_admin_cannot_create_headquarters(self):
        self.login_as(self.hq1_admin)
        response = self.client.post(reverse('headquarters-list'), {'name': 'East HQ', 'code': 'EHQ'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_hq_admin_cannot_update_own_headquarters(self):
        self.login_as(self.hq1_admin)
        response = self.client.patch(reverse('headquarters-detail', args=[self.hq1.id]), {'city': 'Metropolis'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_hq_staff_sees_only_own_headquarters(self):
        self.login_as(self.hq1_staff)
        response = self.client.get(reverse('headquarters-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], self.hq1.id)

    def test_sub_hq_staff_has_no_headquarters_access(self):
        self.login_as(self.hq1_sub_staff)
        response = self.client.get(reverse('headquarters-list'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_mr_has_no_headquarters_access(self):
        self.login_as(self.mr)
        response = self.client.get(reverse('headquarters-list'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_search_filters_by_name_or_code(self):
        self.login_as(self.super_admin)
        response = self.client.get(reverse('headquarters-list'), {'search': 'South'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['code'], 'SHQ')

    def test_ordering_by_name_descending(self):
        self.login_as(self.super_admin)
        response = self.client.get(reverse('headquarters-list'), {'ordering': '-name'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [row['name'] for row in response.data['results']]
        self.assertEqual(names, ['South HQ', 'North HQ'])

    def test_pagination_page_size(self):
        self.login_as(self.super_admin)
        response = self.client.get(reverse('headquarters-list'), {'page_size': 1})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertIsNotNone(response.data['next'])


class SubHeadquartersAPITests(OrganizationsAPITestCase):
    def test_super_admin_sees_all_sub_headquarters(self):
        self.login_as(self.super_admin)
        response = self.client.get(reverse('sub-headquarters-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)

    def test_super_admin_can_create_under_any_headquarters(self):
        self.login_as(self.super_admin)
        response = self.client.post(
            reverse('sub-headquarters-list'),
            {'headquarters': self.hq2.id, 'name': 'South Sub B', 'code': 'SHQ-S2'},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_hq_admin_sees_only_own_headquarters_sub_headquarters(self):
        self.login_as(self.hq1_admin)
        response = self.client.get(reverse('sub-headquarters-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], self.hq1_sub.id)

    def test_hq_admin_can_create_under_own_headquarters(self):
        self.login_as(self.hq1_admin)
        response = self.client.post(
            reverse('sub-headquarters-list'),
            {'headquarters': self.hq1.id, 'name': 'North Sub B', 'code': 'NHQ-S2'},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['created_by'], self.hq1_admin.id)

    def test_hq_admin_cannot_create_under_other_headquarters(self):
        self.login_as(self.hq1_admin)
        response = self.client.post(
            reverse('sub-headquarters-list'),
            {'headquarters': self.hq2.id, 'name': 'Sneaky Sub', 'code': 'SNEAK'},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_hq_admin_can_update_own_headquarters_sub_headquarters(self):
        self.login_as(self.hq1_admin)
        response = self.client.patch(
            reverse('sub-headquarters-detail', args=[self.hq1_sub.id]), {'address': '123 Main St'},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_hq_admin_cannot_update_other_headquarters_sub_headquarters(self):
        self.login_as(self.hq1_admin)
        response = self.client.patch(
            reverse('sub-headquarters-detail', args=[self.hq2_sub.id]), {'address': '123 Main St'},
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_hq_admin_can_delete_own_headquarters_sub_headquarters(self):
        # Use a sub-HQ with no attached User: SubHeadquarters is PROTECTed
        # against deletion while a User still references it (self.hq1_sub
        # has hq1_sub_staff attached).
        empty_sub = SubHeadquarters.objects.create(headquarters=self.hq1, name='North Sub Empty', code='NHQ-S9')
        self.login_as(self.hq1_admin)
        response = self.client.delete(reverse('sub-headquarters-detail', args=[empty_sub.id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_hq_staff_can_read_but_not_create(self):
        self.login_as(self.hq1_staff)
        list_response = self.client.get(reverse('sub-headquarters-list'))
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data['count'], 1)

        create_response = self.client.post(
            reverse('sub-headquarters-list'),
            {'headquarters': self.hq1.id, 'name': 'North Sub B', 'code': 'NHQ-S2'},
        )
        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_sub_hq_staff_sees_only_own_sub_headquarters(self):
        self.login_as(self.hq1_sub_staff)
        response = self.client.get(reverse('sub-headquarters-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], self.hq1_sub.id)

    def test_sub_hq_staff_cannot_retrieve_other_sub_headquarters(self):
        self.login_as(self.hq1_sub_staff)
        response = self.client.get(reverse('sub-headquarters-detail', args=[self.hq2_sub.id]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_mr_has_no_sub_headquarters_access(self):
        self.login_as(self.mr)
        response = self.client.get(reverse('sub-headquarters-list'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_search_filters_by_name(self):
        self.login_as(self.super_admin)
        response = self.client.get(reverse('sub-headquarters-list'), {'search': 'South Sub A'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['code'], 'SHQ-S1')

    def test_filter_by_headquarters(self):
        self.login_as(self.super_admin)
        response = self.client.get(reverse('sub-headquarters-list'), {'headquarters': self.hq2.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], self.hq2_sub.id)
