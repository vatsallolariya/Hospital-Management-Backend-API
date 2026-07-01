import logging

from django.db.models import Q
from rest_framework import viewsets
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import AuthenticationFailed, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from common.mixins import AuditLogMixin

from .models import Role, User
from .permissions import UserPermission
from .serializers import CustomTokenObtainPairSerializer, MeSerializer, UserSerializer

logger = logging.getLogger(__name__)


class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        try:
            response = super().post(request, *args, **kwargs)
        except AuthenticationFailed:
            logger.warning('Login failed for email=%s: invalid credentials', email)
            raise
        logger.info('Login succeeded for email=%s', email)
        return response


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh = request.data.get('refresh')
        if not refresh:
            return Response({'detail': 'refresh token is required.'}, status=400)
        try:
            token = RefreshToken(refresh)
            token.blacklist()
        except TokenError:
            logger.warning('Logout failed for user=%s: invalid or expired refresh token', request.user)
            return Response({'detail': 'Invalid or expired refresh token.'}, status=400)
        logger.info('Logout succeeded for user=%s', request.user)
        return Response(status=204)


class MeView(RetrieveAPIView):
    serializer_class = MeSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class UserViewSet(AuditLogMixin, viewsets.ModelViewSet):
    """
    Per §4: Super Admin manages all users; HQ Admin manages HQ Staff, Sub HQ
    Staff, and MR accounts under their own Headquarters. No other role has a
    "manage users" duty, so the queryset/permission scoping below only ever
    needs to account for these two roles (see UserPermission).
    """
    queryset = User.objects.select_related('headquarters', 'sub_headquarters', 'created_by').all()
    serializer_class = UserSerializer
    permission_classes = [UserPermission]
    filterset_fields = ['role', 'headquarters', 'sub_headquarters', 'is_active']
    search_fields = ['email', 'first_name', 'last_name', 'phone']
    ordering_fields = ['email', 'date_joined', 'role']
    ordering = ['email']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == Role.SUPER_ADMIN:
            return qs
        if user.role == Role.HQ_ADMIN:
            return qs.filter(role__in=(Role.HQ_STAFF, Role.SUB_HQ_STAFF, Role.MR)).filter(
                Q(headquarters_id=user.headquarters_id) | Q(sub_headquarters__headquarters_id=user.headquarters_id)
            )
        return qs.none()

    def perform_create(self, serializer):
        super().perform_create(serializer)
        self.audit_logger.info(
            'Created User id=%s email=%s by user=%s', serializer.instance.pk, serializer.instance.email, self.request.user,
        )
