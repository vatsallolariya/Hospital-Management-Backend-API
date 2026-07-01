from rest_framework import viewsets

from accounts.models import Role
from common.mixins import AuditLogMixin

from .models import Headquarters, SubHeadquarters
from .permissions import HeadquartersPermission, SubHeadquartersPermission
from .serializers import HeadquartersSerializer, SubHeadquartersSerializer


class HeadquartersViewSet(AuditLogMixin, viewsets.ModelViewSet):
    queryset = Headquarters.objects.all()
    serializer_class = HeadquartersSerializer
    permission_classes = [HeadquartersPermission]
    filterset_fields = ['is_active', 'city', 'state']
    search_fields = ['name', 'code', 'city', 'state']
    ordering_fields = ['name', 'code', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == Role.SUPER_ADMIN:
            return qs
        if user.role in (Role.HQ_ADMIN, Role.HQ_STAFF):
            return qs.filter(pk=user.headquarters_id)
        return qs.none()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
        self.audit_logger.info(
            'Created Headquarters id=%s by user=%s', serializer.instance.pk, self.request.user,
        )


class SubHeadquartersViewSet(AuditLogMixin, viewsets.ModelViewSet):
    queryset = SubHeadquarters.objects.select_related('headquarters').all()
    serializer_class = SubHeadquartersSerializer
    permission_classes = [SubHeadquartersPermission]
    filterset_fields = ['headquarters', 'is_active']
    search_fields = ['name', 'code']
    ordering_fields = ['name', 'code', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == Role.SUPER_ADMIN:
            return qs
        if user.role in (Role.HQ_ADMIN, Role.HQ_STAFF):
            return qs.filter(headquarters_id=user.headquarters_id)
        if user.role == Role.SUB_HQ_STAFF:
            return qs.filter(pk=user.sub_headquarters_id)
        return qs.none()

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
        self.audit_logger.info(
            'Created SubHeadquarters id=%s by user=%s', serializer.instance.pk, self.request.user,
        )
