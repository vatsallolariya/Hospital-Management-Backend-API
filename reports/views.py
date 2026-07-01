import django_filters
from django.db.models import Q
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from common.mixins import HierarchyScopedQuerysetMixin
from visits.models import Visit
from visits.serializers import VisitSerializer


class VisitReportFilterSet(django_filters.FilterSet):
    start_date = django_filters.DateFilter(field_name='visit_date', lookup_expr='gte')
    end_date = django_filters.DateFilter(field_name='visit_date', lookup_expr='lte')
    headquarters = django_filters.NumberFilter(method='filter_headquarters')
    sub_headquarters = django_filters.NumberFilter(field_name='doctor__sub_headquarters_id')

    class Meta:
        model = Visit
        fields = ['status', 'doctor', 'mr']

    def filter_headquarters(self, queryset, name, value):
        return queryset.filter(
            Q(doctor__headquarters_id=value) | Q(doctor__sub_headquarters__headquarters_id=value)
        )


class VisitReportView(HierarchyScopedQuerysetMixin, generics.ListAPIView):
    """
    Per §5/§4: read-only, filtered/paginated/sortable report over Visits,
    scoped to the requesting user's role/hierarchy position (same scoping as
    VisitViewSet in visits/views.py).
    """
    queryset = Visit.objects.select_related('doctor', 'mr').all()
    serializer_class = VisitSerializer
    permission_classes = [IsAuthenticated]
    hq_lookup_field = 'doctor__headquarters'
    sub_hq_lookup_field = 'doctor__sub_headquarters'
    filterset_class = VisitReportFilterSet
    search_fields = ['doctor__name', 'mr__email', 'purpose', 'remarks']
    ordering_fields = ['visit_date', 'status', 'created_at']
    ordering = ['-visit_date']

    def scope_queryset_to_mr(self, qs, user):
        return qs.filter(mr_id=user.id)
