from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models


class Role(models.TextChoices):
    SUPER_ADMIN = 'SUPER_ADMIN', 'Super Admin'
    HQ_ADMIN = 'HQ_ADMIN', 'HQ Admin'
    HQ_STAFF = 'HQ_STAFF', 'HQ Staff'
    SUB_HQ_STAFF = 'SUB_HQ_STAFF', 'Sub HQ Staff'
    MR = 'MR', 'Medical Rep'


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('Users must have an email address')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.full_clean(exclude=['password'])
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        extra_fields.setdefault('role', Role.MR)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', Role.SUPER_ADMIN)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=20, blank=True)

    role = models.CharField(max_length=20, choices=Role.choices)
    headquarters = models.ForeignKey(
        'organizations.Headquarters', on_delete=models.PROTECT,
        null=True, blank=True, related_name='users',
    )
    sub_headquarters = models.ForeignKey(
        'organizations.SubHeadquarters', on_delete=models.PROTECT,
        null=True, blank=True, related_name='users',
    )

    created_by = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_users',
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        indexes = [
            models.Index(fields=['role']),
            models.Index(fields=['headquarters']),
            models.Index(fields=['sub_headquarters']),
        ]

    def __str__(self):
        return f'{self.email} ({self.get_role_display()})'

    def clean(self):
        super().clean()

        if self.role == Role.SUPER_ADMIN:
            if self.headquarters_id or self.sub_headquarters_id:
                raise ValidationError('Super Admin must not be scoped to a Headquarters or Sub Headquarters.')
        elif self.role in (Role.HQ_ADMIN, Role.HQ_STAFF):
            if not self.headquarters_id:
                raise ValidationError(f'{self.get_role_display()} requires a Headquarters.')
            if self.sub_headquarters_id:
                raise ValidationError(f'{self.get_role_display()} must not have a Sub Headquarters.')
        elif self.role == Role.SUB_HQ_STAFF:
            if not self.sub_headquarters_id:
                raise ValidationError('Sub HQ Staff requires a Sub Headquarters.')
            if self.headquarters_id:
                raise ValidationError('Sub HQ Staff must not have a Headquarters.')
        elif self.role == Role.MR:
            if bool(self.headquarters_id) == bool(self.sub_headquarters_id):
                raise ValidationError('Medical Rep requires exactly one of Headquarters or Sub Headquarters.')
