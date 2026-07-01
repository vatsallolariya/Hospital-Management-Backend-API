from django.db import IntegrityError, transaction
from django.test import TestCase

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
