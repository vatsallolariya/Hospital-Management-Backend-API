import django_filters
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from common.mixins import AuditLogMixin, HierarchyScopedQuerysetMixin

from .models import Visit, VisitStatus
from .permissions import VisitPermission
from .serializers import VisitSerializer


class VisitFilterSet(django_filters.FilterSet):
    date = django_filters.DateFilter(field_name='visit_date')

    class Meta:
        model = Visit
        fields = ['status', 'doctor', 'mr', 'date']


class VisitViewSet(HierarchyScopedQuerysetMixin, AuditLogMixin, viewsets.ModelViewSet):
    queryset = Visit.objects.select_related('doctor', 'mr').all()
    serializer_class = VisitSerializer
    permission_classes = [VisitPermission]
    hq_lookup_field = 'doctor__headquarters'
    sub_hq_lookup_field = 'doctor__sub_headquarters'
    filterset_class = VisitFilterSet
    search_fields = ['doctor__name', 'mr__email', 'purpose', 'remarks']
    ordering_fields = ['visit_date', 'created_at']
    ordering = ['-visit_date']

    def scope_queryset_to_mr(self, qs, user):
        """MR sees only their own Visits."""
        return qs.filter(mr_id=user.id)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        self.audit_logger.info(
            'Created Visit id=%s by user=%s', serializer.instance.pk, self.request.user,
        )

    @action(detail=True, methods=['post'], url_path='mark-visit')
    def mark_visit(self, request, pk=None):
        visit = self.get_object()
        if visit.status != VisitStatus.PENDING:
            self.audit_logger.warning(
                'Rejected mark-visit on Visit id=%s status=%s by user=%s', visit.pk, visit.status, request.user,
            )
            return Response(
                {'detail': f'Cannot mark a {visit.status.lower()} visit as completed.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        visit.status = VisitStatus.COMPLETED
        visit.check_in_time = timezone.now()
        if 'remarks' in request.data:
            visit.remarks = request.data['remarks']
        if 'purpose' in request.data:
            visit.purpose = request.data['purpose']
        visit.save()
        self.audit_logger.info('Marked Visit id=%s completed by user=%s', visit.pk, request.user)
        return Response(self.get_serializer(visit).data)
