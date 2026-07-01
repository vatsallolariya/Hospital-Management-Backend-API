from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ['email']
    list_display = ['email', 'first_name', 'last_name', 'role', 'headquarters', 'sub_headquarters', 'is_active', 'is_staff']
    list_filter = ['role', 'is_active', 'is_staff', 'headquarters', 'sub_headquarters']
    search_fields = ['email', 'first_name', 'last_name', 'phone']
    filter_horizontal = ['groups', 'user_permissions']

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'phone')}),
        ('Hierarchy', {'fields': ('role', 'headquarters', 'sub_headquarters', 'created_by')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('date_joined', 'updated_at')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'role', 'headquarters', 'sub_headquarters'),
        }),
    )
    readonly_fields = ['date_joined', 'updated_at']
