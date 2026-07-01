from django.contrib import admin

from .models import Headquarters, SubHeadquarters


@admin.register(Headquarters)
class HeadquartersAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'city', 'state', 'is_active', 'created_by']
    list_filter = ['is_active', 'state']
    search_fields = ['name', 'code', 'city']


@admin.register(SubHeadquarters)
class SubHeadquartersAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'headquarters', 'is_active', 'created_by']
    list_filter = ['is_active', 'headquarters']
    search_fields = ['name', 'code']
