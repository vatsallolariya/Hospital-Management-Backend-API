from rest_framework import viewsets

from common.mixins import HierarchyScopedQuerysetMixin

from .models import Doctor
from .permissions import DoctorPermission
from .serializers import DoctorSerializer


class DoctorViewSet(HierarchyScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = Doctor.objects.select_related('headquarters', 'sub_headquarters', 'assigned_mr').all()
    serializer_class = DoctorSerializer
    permission_classes = [DoctorPermission]
    filterset_fields = ['headquarters', 'sub_headquarters', 'assigned_mr', 'is_active', 'specialization']
    search_fields = ['name', 'specialization', 'clinic_name', 'email', 'phone']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    def scope_queryset_to_mr(self, qs, user):
        """MR sees only their own assigned Doctors, not the whole HQ/Sub HQ (per §4)."""
        return qs.filter(assigned_mr_id=user.id)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
