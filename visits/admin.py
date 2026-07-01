from django.contrib import admin

from .models import Visit


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = ['doctor', 'mr', 'visit_date', 'status', 'check_in_time']
    list_filter = ['status', 'visit_date']
    search_fields = ['doctor__name', 'mr__email', 'purpose']
    date_hierarchy = 'visit_date'
