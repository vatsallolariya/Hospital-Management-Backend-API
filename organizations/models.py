from django.conf import settings
from django.db import models


class Headquarters(models.Model):
    name = models.CharField(max_length=255, unique=True)
    code = models.CharField(max_length=20, unique=True)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_headquarters',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Headquarters'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.code})'


class SubHeadquarters(models.Model):
    headquarters = models.ForeignKey(
        Headquarters, on_delete=models.CASCADE, related_name='sub_headquarters',
    )
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=20)
    address = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_sub_headquarters',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Sub Headquarters'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['headquarters', 'code'], name='unique_sub_hq_code_per_hq'),
        ]

    def __str__(self):
        return f'{self.name} ({self.code}) — {self.headquarters.code}'
