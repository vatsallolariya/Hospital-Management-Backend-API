"""
Shared factory_boy factories for building the HQ -> Sub HQ -> User ->
Doctor -> Visit hierarchy in tests.
"""
from django.utils import timezone
import factory
from factory.django import DjangoModelFactory

from accounts.models import Role, User
from doctors.models import Doctor
from organizations.models import Headquarters, SubHeadquarters
from visits.models import Visit


class HeadquartersFactory(DjangoModelFactory):
    class Meta:
        model = Headquarters

    name = factory.Sequence(lambda n: f'Headquarters {n}')
    code = factory.Sequence(lambda n: f'HQ{n}')


class SubHeadquartersFactory(DjangoModelFactory):
    class Meta:
        model = SubHeadquarters

    headquarters = factory.SubFactory(HeadquartersFactory)
    name = factory.Sequence(lambda n: f'Sub Headquarters {n}')
    code = factory.Sequence(lambda n: f'SUB{n}')


class UserFactory(DjangoModelFactory):
    """
    Base MR factory. Uses `User.objects.create_user` so passwords are hashed
    and role/scope validation runs. Use the per-role subclasses below.
    """
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f'user{n}@example.com')
    role = Role.MR
    headquarters = factory.SubFactory(HeadquartersFactory)
    password = 'pass12345'

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        password = kwargs.pop('password')
        manager = cls._get_manager(model_class)
        return manager.create_user(*args, password=password, **kwargs)


class SuperAdminFactory(UserFactory):
    role = Role.SUPER_ADMIN
    headquarters = None

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        password = kwargs.pop('password')
        manager = cls._get_manager(model_class)
        return manager.create_superuser(*args, password=password, **kwargs)


class HQAdminFactory(UserFactory):
    role = Role.HQ_ADMIN


class HQStaffFactory(UserFactory):
    role = Role.HQ_STAFF


class SubHQStaffFactory(UserFactory):
    role = Role.SUB_HQ_STAFF
    headquarters = None
    sub_headquarters = factory.SubFactory(SubHeadquartersFactory)


class MRFactory(UserFactory):
    role = Role.MR


class DoctorFactory(DjangoModelFactory):
    class Meta:
        model = Doctor

    name = factory.Sequence(lambda n: f'Dr. Test {n}')
    headquarters = factory.SubFactory(HeadquartersFactory)


class VisitFactory(DjangoModelFactory):
    class Meta:
        model = Visit

    doctor = factory.SubFactory(DoctorFactory)
    mr = factory.SubFactory(MRFactory)
    visit_date = factory.LazyFunction(timezone.localdate)
