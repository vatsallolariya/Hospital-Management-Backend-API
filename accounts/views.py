from django.db.models import Q
from rest_framework import viewsets
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import Role, User
from .permissions import UserPermission
from .serializers import CustomTokenObtainPairSerializer, MeSerializer, UserSerializer


class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


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
            return Response({'detail': 'Invalid or expired refresh token.'}, status=400)
        return Response(status=204)


class MeView(RetrieveAPIView):
    serializer_class = MeSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class UserViewSet(viewsets.ModelViewSet):
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
