"""Root URL configuration: routes each API prefix to its app."""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/auth/', include('accounts.urls')),
    path('api/v1/', include('accounts.user_urls')),
    path('api/v1/', include('organizations.urls')),
    path('api/v1/', include('doctors.urls')),
    path('api/v1/', include('visits.urls')),
    path('api/v1/', include('dashboard.urls')),
    path('api/v1/', include('reports.urls')),
]
