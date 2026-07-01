from django.contrib import admin

from .models import Doctor


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ['name', 'specialization', 'headquarters', 'sub_headquarters', 'assigned_mr', 'is_active']
    list_filter = ['is_active', 'specialization', 'headquarters', 'sub_headquarters']
    search_fields = ['name', 'clinic_name', 'email', 'phone']
