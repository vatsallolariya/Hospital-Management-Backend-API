from django.urls import path

from .views import VisitReportView

urlpatterns = [
    path('reports/visits/', VisitReportView.as_view(), name='report-visits'),
]
