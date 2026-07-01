from django.core.exceptions import ValidationError
from django.test import TestCase

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
