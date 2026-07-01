from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Doctor(models.Model):
    name = models.CharField(max_length=255)
    specialization = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    clinic_name = models.CharField(max_length=255, blank=True)
    address = models.CharField(max_length=255, blank=True)

    headquarters = models.ForeignKey(
        'organizations.Headquarters', on_delete=models.CASCADE,
        null=True, blank=True, related_name='doctors',
    )
    sub_headquarters = models.ForeignKey(
        'organizations.SubHeadquarters', on_delete=models.CASCADE,
        null=True, blank=True, related_name='doctors',
    )
    assigned_mr = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='assigned_doctors',
        limit_choices_to={'role': 'MR'},
    )

    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_doctors',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['headquarters']),
            models.Index(fields=['sub_headquarters']),
            models.Index(fields=['assigned_mr']),
        ]
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(headquarters__isnull=False, sub_headquarters__isnull=True)
                    | models.Q(headquarters__isnull=True, sub_headquarters__isnull=False)
                ),
                name='doctor_exactly_one_parent',
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()

        if bool(self.headquarters_id) == bool(self.sub_headquarters_id):
            raise ValidationError('Doctor requires exactly one of Headquarters or Sub Headquarters.')

        if self.assigned_mr_id and self.assigned_mr.role != 'MR':
            raise ValidationError('assigned_mr must be a user with role MR.')
