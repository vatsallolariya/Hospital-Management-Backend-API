from django.conf import settings
from django.db import models


class VisitStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    COMPLETED = 'COMPLETED', 'Completed'
    CANCELLED = 'CANCELLED', 'Cancelled'


class Visit(models.Model):
    doctor = models.ForeignKey(
        'doctors.Doctor', on_delete=models.CASCADE, related_name='visits',
    )
    mr = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='visits', limit_choices_to={'role': 'MR'},
    )
    visit_date = models.DateField()
    status = models.CharField(max_length=20, choices=VisitStatus.choices, default=VisitStatus.PENDING)
    check_in_time = models.DateTimeField(null=True, blank=True)
    purpose = models.CharField(max_length=255, blank=True)
    remarks = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-visit_date']
        indexes = [
            models.Index(fields=['visit_date', 'status'], name='visit_date_status_idx'),
            models.Index(fields=['mr']),
        ]

    def __str__(self):
        return f'{self.doctor} — {self.visit_date} ({self.status})'
