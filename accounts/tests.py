from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import Role, User
from organizations.models import Headquarters, SubHeadquarters


class UserModelTests(TestCase):
    def setUp(self):
        self.hq = Headquarters.objects.create(name='North HQ', code='NHQ')
        self.sub_hq = SubHeadquarters.objects.create(headquarters=self.hq, name='North Sub', code='NHQ-S1')

    def test_create_user_defaults_to_mr_role(self):
        user = User.objects.create_user(email='mr@example.com', password='pass12345', headquarters=self.hq)
        self.assertEqual(user.role, Role.MR)
        self.assertTrue(user.check_password('pass12345'))
        self.assertFalse(user.is_staff)

    def test_create_superuser_sets_super_admin_flags(self):
        admin = User.objects.create_superuser(email='root@example.com', password='pass12345')
        self.assertEqual(admin.role, Role.SUPER_ADMIN)
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

    def test_str_includes_email_and_role(self):
        admin = User.objects.create_superuser(email='root2@example.com', password='pass12345')
        self.assertIn('root2@example.com', str(admin))
        self.assertIn('Super Admin', str(admin))

    def test_super_admin_cannot_have_headquarters(self):
        user = User(email='bad@example.com', role=Role.SUPER_ADMIN, headquarters=self.hq)
        user.set_password('pass12345')
        with self.assertRaises(ValidationError):
            user.full_clean(exclude=['password'])

    def test_hq_admin_requires_headquarters(self):
        user = User(email='hqadmin@example.com', role=Role.HQ_ADMIN)
        user.set_password('pass12345')
        with self.assertRaises(ValidationError):
            user.full_clean(exclude=['password'])

    def test_hq_admin_cannot_also_have_sub_headquarters(self):
        user = User(email='hqadmin2@example.com', role=Role.HQ_ADMIN, headquarters=self.hq, sub_headquarters=self.sub_hq)
        user.set_password('pass12345')
        with self.assertRaises(ValidationError):
            user.full_clean(exclude=['password'])

    def test_sub_hq_staff_requires_sub_headquarters(self):
        user = User(email='substaff@example.com', role=Role.SUB_HQ_STAFF)
        user.set_password('pass12345')
        with self.assertRaises(ValidationError):
            user.full_clean(exclude=['password'])

    def test_mr_requires_exactly_one_scope(self):
        neither = User(email='mr1@example.com', role=Role.MR)
        neither.set_password('pass12345')
        with self.assertRaises(ValidationError):
            neither.full_clean(exclude=['password'])

        both = User(email='mr2@example.com', role=Role.MR, headquarters=self.hq, sub_headquarters=self.sub_hq)
        both.set_password('pass12345')
        with self.assertRaises(ValidationError):
            both.full_clean(exclude=['password'])

        valid = User(email='mr3@example.com', role=Role.MR, headquarters=self.hq)
        valid.set_password('pass12345')
        valid.full_clean(exclude=['password'])  # should not raise


class AuthAPITests(APITestCase):
    PASSWORD = 'pass12345'

    def setUp(self):
        self.hq = Headquarters.objects.create(name='East HQ', code='EHQ')
        self.sub_hq = SubHeadquarters.objects.create(headquarters=self.hq, name='East Sub', code='EHQ-S1')

        self.super_admin = User.objects.create_superuser(email='super@example.com', password=self.PASSWORD)
        self.hq_admin = User.objects.create_user(
            email='hqadmin@example.com', password=self.PASSWORD, role=Role.HQ_ADMIN, headquarters=self.hq,
        )
        self.hq_staff = User.objects.create_user(
            email='hqstaff@example.com', password=self.PASSWORD, role=Role.HQ_STAFF, headquarters=self.hq,
        )
        self.sub_hq_staff = User.objects.create_user(
            email='subhqstaff@example.com', password=self.PASSWORD, role=Role.SUB_HQ_STAFF, sub_headquarters=self.sub_hq,
        )
        self.mr = User.objects.create_user(
            email='mr@example.com', password=self.PASSWORD, role=Role.MR, headquarters=self.hq,
        )

    def login(self, email):
        response = self.client.post(reverse('auth-login'), {'email': email, 'password': self.PASSWORD})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data

    def test_login_success_returns_access_and_refresh(self):
        tokens = self.login('super@example.com')
        self.assertIn('access', tokens)
        self.assertIn('refresh', tokens)

    def test_login_failure_wrong_password(self):
        response = self.client.post(reverse('auth-login'), {'email': 'super@example.com', 'password': 'wrong'})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_failure_inactive_user(self):
        self.mr.is_active = False
        self.mr.save()
        response = self.client.post(reverse('auth-login'), {'email': 'mr@example.com', 'password': self.PASSWORD})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_refresh_returns_new_access_token(self):
        tokens = self.login('super@example.com')
        response = self.client.post(reverse('auth-refresh'), {'refresh': tokens['refresh']})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    def test_logout_blacklists_refresh_token(self):
        tokens = self.login('super@example.com')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')

        logout_response = self.client.post(reverse('auth-logout'), {'refresh': tokens['refresh']})
        self.assertEqual(logout_response.status_code, status.HTTP_204_NO_CONTENT)

        refresh_response = self.client.post(reverse('auth-refresh'), {'refresh': tokens['refresh']})
        self.assertEqual(refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_requires_authentication(self):
        response = self.client.get(reverse('auth-me'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_rejects_expired_access_token(self):
        token = AccessToken.for_user(self.super_admin)
        token.set_exp(lifetime=timedelta(seconds=-1))
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.get(reverse('auth-me'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_returns_correct_role_and_scope_per_role(self):
        cases = [
            (self.super_admin, Role.SUPER_ADMIN, None, None),
            (self.hq_admin, Role.HQ_ADMIN, self.hq.id, None),
            (self.hq_staff, Role.HQ_STAFF, self.hq.id, None),
            (self.sub_hq_staff, Role.SUB_HQ_STAFF, None, self.sub_hq.id),
            (self.mr, Role.MR, self.hq.id, None),
        ]
        for user, expected_role, expected_hq, expected_sub_hq in cases:
            tokens = self.login(user.email)
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')

            response = self.client.get(reverse('auth-me'))

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data['email'], user.email)
            self.assertEqual(response.data['role'], expected_role)
            self.assertEqual(response.data['headquarters'], expected_hq)
            self.assertEqual(response.data['sub_headquarters'], expected_sub_hq)

            self.client.credentials()


class UserAPITests(APITestCase):
    PASSWORD = 'pass12345'

    def setUp(self):
        self.hq = Headquarters.objects.create(name='West HQ', code='WHQ')
        self.other_hq = Headquarters.objects.create(name='Other HQ', code='OHQ')
        self.sub_hq = SubHeadquarters.objects.create(headquarters=self.hq, name='West Sub', code='WHQ-S1')

        self.super_admin = User.objects.create_superuser(email='super2@example.com', password=self.PASSWORD)
        self.hq_admin = User.objects.create_user(
            email='hqadmin2@example.com', password=self.PASSWORD, role=Role.HQ_ADMIN, headquarters=self.hq,
        )
        self.hq_staff = User.objects.create_user(
            email='hqstaff2@example.com', password=self.PASSWORD, role=Role.HQ_STAFF, headquarters=self.hq,
        )

    def login(self, email):
        response = self.client.post(reverse('auth-login'), {'email': email, 'password': self.PASSWORD})
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')

    def test_hq_admin_can_create_hq_staff_under_own_hq(self):
        self.login('hqadmin2@example.com')
        response = self.client.post(reverse('user-list'), {
            'email': 'newstaff@example.com', 'password': 'pass12345',
            'role': Role.HQ_STAFF, 'headquarters': self.hq.id,
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn('password', response.data)
        created = User.objects.get(email='newstaff@example.com')
        self.assertTrue(created.check_password('pass12345'))
        self.assertEqual(created.created_by, self.hq_admin)

    def test_hq_admin_cannot_create_user_under_other_hq(self):
        self.login('hqadmin2@example.com')
        response = self.client.post(reverse('user-list'), {
            'email': 'newstaff2@example.com', 'password': 'pass12345',
            'role': Role.HQ_STAFF, 'headquarters': self.other_hq.id,
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_hq_admin_cannot_create_super_admin(self):
        self.login('hqadmin2@example.com')
        response = self.client.post(reverse('user-list'), {
            'email': 'escalate1@example.com', 'password': 'pass12345', 'role': Role.SUPER_ADMIN,
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_hq_admin_cannot_create_hq_admin(self):
        self.login('hqadmin2@example.com')
        response = self.client.post(reverse('user-list'), {
            'email': 'escalate2@example.com', 'password': 'pass12345', 'role': Role.HQ_ADMIN,
            'headquarters': self.hq.id,
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_super_admin_can_create_any_role(self):
        self.login('super2@example.com')
        response = self.client.post(reverse('user-list'), {
            'email': 'newadmin@example.com', 'password': 'pass12345',
            'role': Role.HQ_ADMIN, 'headquarters': self.other_hq.id,
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_invalid_role_org_combo_returns_400_not_500(self):
        self.login('super2@example.com')
        response = self.client.post(reverse('user-list'), {
            'email': 'badcombo@example.com', 'password': 'pass12345',
            'role': Role.MR, 'headquarters': self.hq.id, 'sub_headquarters': self.sub_hq.id,
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_hq_staff_cannot_access_user_endpoint(self):
        self.login('hqstaff2@example.com')
        response = self.client.get(reverse('user-list'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
