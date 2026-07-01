from datetime import date

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role, User
from doctors.models import Doctor
from organizations.models import Headquarters, SubHeadquarters
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


class VisitAPITestCase(APITestCase):
    """Shared fixtures for Visit CRUD + RBAC tests."""

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

        self.visit_hq1 = Visit.objects.create(doctor=self.doc_hq1, mr=self.mr_hq1, visit_date=date(2026, 1, 1))
        self.visit_hq1_sub = Visit.objects.create(doctor=self.doc_hq1_sub, mr=self.mr_hq1_sub, visit_date=date(2026, 1, 2))
        self.visit_hq2 = Visit.objects.create(doctor=self.doc_hq2, mr=self.mr_hq2, visit_date=date(2026, 1, 3))

    def login_as(self, user):
        response = self.client.post(reverse('auth-login'), {'email': user.email, 'password': self.PASSWORD})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')


class VisitListRetrieveTests(VisitAPITestCase):
    def test_super_admin_sees_all_visits(self):
        self.login_as(self.super_admin)
        response = self.client.get(reverse('visit-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 3)

    def test_hq_admin_sees_own_hq_and_own_sub_hq_visits(self):
        self.login_as(self.hq1_admin)
        response = self.client.get(reverse('visit-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {row['id'] for row in response.data['results']}
        self.assertEqual(ids, {self.visit_hq1.id, self.visit_hq1_sub.id})

    def test_hq_staff_sees_only_visits_directly_under_own_hq(self):
        self.login_as(self.hq1_staff)
        response = self.client.get(reverse('visit-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], self.visit_hq1.id)

    def test_sub_hq_staff_sees_only_own_sub_hq_visits(self):
        self.login_as(self.hq1_sub_staff)
        response = self.client.get(reverse('visit-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], self.visit_hq1_sub.id)

    def test_mr_sees_only_own_visits(self):
        self.login_as(self.mr_hq1)
        response = self.client.get(reverse('visit-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], self.visit_hq1.id)

    def test_mr_cannot_retrieve_other_mr_visit(self):
        self.login_as(self.mr_hq1)
        response = self.client.get(reverse('visit-detail', args=[self.visit_hq2.id]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_filter_by_status(self):
        self.login_as(self.super_admin)
        self.visit_hq2.status = VisitStatus.CANCELLED
        self.visit_hq2.save()
        response = self.client.get(reverse('visit-list'), {'status': 'CANCELLED'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], self.visit_hq2.id)

    def test_filter_by_date(self):
        self.login_as(self.super_admin)
        response = self.client.get(reverse('visit-list'), {'date': '2026-01-02'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], self.visit_hq1_sub.id)

    def test_filter_by_doctor(self):
        self.login_as(self.super_admin)
        response = self.client.get(reverse('visit-list'), {'doctor': self.doc_hq2.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], self.visit_hq2.id)

    def test_search_by_doctor_name(self):
        self.login_as(self.super_admin)
        response = self.client.get(reverse('visit-list'), {'search': 'Hq2'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], self.visit_hq2.id)

    def test_ordering_by_visit_date_ascending(self):
        self.login_as(self.super_admin)
        response = self.client.get(reverse('visit-list'), {'ordering': 'visit_date'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        dates = [row['visit_date'] for row in response.data['results']]
        self.assertEqual(dates, sorted(dates))


class VisitCreateUpdateDeleteTests(VisitAPITestCase):
    def test_mr_can_create_visit_for_own_assigned_doctor(self):
        self.login_as(self.mr_hq1)
        response = self.client.post(
            reverse('visit-list'), {'doctor': self.doc_hq1.id, 'visit_date': '2026-02-01'},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['mr'], self.mr_hq1.id)

    def test_mr_cannot_create_visit_for_unassigned_doctor(self):
        self.login_as(self.mr_hq1)
        response = self.client.post(
            reverse('visit-list'), {'doctor': self.doc_hq2.id, 'visit_date': '2026-02-01'},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_mr_supplied_mr_field_is_ignored_and_forced_to_self(self):
        self.login_as(self.mr_hq1)
        response = self.client.post(
            reverse('visit-list'),
            {'doctor': self.doc_hq1.id, 'visit_date': '2026-02-01', 'mr': self.mr_hq2.id},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['mr'], self.mr_hq1.id)

    def test_hq_admin_cannot_create_visit(self):
        self.login_as(self.hq1_admin)
        response = self.client.post(
            reverse('visit-list'), {'doctor': self.doc_hq1.id, 'mr': self.mr_hq1.id, 'visit_date': '2026-02-01'},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_hq_staff_can_create_visit_within_own_hq(self):
        self.login_as(self.hq1_staff)
        response = self.client.post(
            reverse('visit-list'), {'doctor': self.doc_hq1.id, 'mr': self.mr_hq1.id, 'visit_date': '2026-02-01'},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_hq_staff_cannot_create_visit_outside_own_hq(self):
        self.login_as(self.hq1_staff)
        response = self.client.post(
            reverse('visit-list'), {'doctor': self.doc_hq2.id, 'mr': self.mr_hq2.id, 'visit_date': '2026-02-01'},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_sub_hq_staff_can_create_visit_within_own_sub_hq(self):
        self.login_as(self.hq1_sub_staff)
        response = self.client.post(
            reverse('visit-list'),
            {'doctor': self.doc_hq1_sub.id, 'mr': self.mr_hq1_sub.id, 'visit_date': '2026-02-01'},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_super_admin_can_create_visit_anywhere(self):
        self.login_as(self.super_admin)
        response = self.client.post(
            reverse('visit-list'), {'doctor': self.doc_hq2.id, 'mr': self.mr_hq2.id, 'visit_date': '2026-02-01'},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_mr_can_update_own_visit_remarks(self):
        self.login_as(self.mr_hq1)
        response = self.client.patch(reverse('visit-detail', args=[self.visit_hq1.id]), {'remarks': 'Discussed new product'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['remarks'], 'Discussed new product')

    def test_mr_cannot_update_other_mr_visit(self):
        self.login_as(self.mr_hq1)
        response = self.client.patch(reverse('visit-detail', args=[self.visit_hq2.id]), {'remarks': 'Sneaky'})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_hq_admin_can_update_but_not_create(self):
        self.login_as(self.hq1_admin)
        response = self.client.patch(reverse('visit-detail', args=[self.visit_hq1.id]), {'remarks': 'Reviewed'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_hq_admin_cannot_delete_visit(self):
        self.login_as(self.hq1_admin)
        response = self.client.delete(reverse('visit-detail', args=[self.visit_hq1.id]))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_mr_cannot_delete_visit(self):
        self.login_as(self.mr_hq1)
        response = self.client.delete(reverse('visit-detail', args=[self.visit_hq1.id]))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_hq_staff_can_delete_own_hq_visit(self):
        self.login_as(self.hq1_staff)
        response = self.client.delete(reverse('visit-detail', args=[self.visit_hq1.id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


class VisitStatusTransitionTests(VisitAPITestCase):
    def test_direct_patch_cannot_set_completed(self):
        self.login_as(self.mr_hq1)
        response = self.client.patch(reverse('visit-detail', args=[self.visit_hq1.id]), {'status': 'COMPLETED'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_pending_can_be_cancelled_via_patch(self):
        self.login_as(self.mr_hq1)
        response = self.client.patch(reverse('visit-detail', args=[self.visit_hq1.id]), {'status': 'CANCELLED'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'CANCELLED')

    def test_cannot_change_status_of_already_cancelled_visit(self):
        self.visit_hq1.status = VisitStatus.CANCELLED
        self.visit_hq1.save()
        self.login_as(self.mr_hq1)
        response = self.client.patch(reverse('visit-detail', args=[self.visit_hq1.id]), {'status': 'PENDING'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_mark_visit_transitions_pending_to_completed_and_sets_checkin(self):
        self.login_as(self.mr_hq1)
        response = self.client.post(reverse('visit-mark-visit', args=[self.visit_hq1.id]), {'remarks': 'Visited clinic'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'COMPLETED')
        self.assertIsNotNone(response.data['check_in_time'])
        self.assertEqual(response.data['remarks'], 'Visited clinic')

    def test_mark_visit_on_cancelled_visit_rejected(self):
        self.visit_hq1.status = VisitStatus.CANCELLED
        self.visit_hq1.save()
        self.login_as(self.mr_hq1)
        response = self.client.post(reverse('visit-mark-visit', args=[self.visit_hq1.id]))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_mark_visit_by_other_mr_not_found(self):
        self.login_as(self.mr_hq2)
        response = self.client.post(reverse('visit-mark-visit', args=[self.visit_hq1.id]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
