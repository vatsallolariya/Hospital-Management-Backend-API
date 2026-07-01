from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Adds role/scope claims to the access token so API consumers don't need
    a separate call just to know what a token can do."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        token['headquarters_id'] = user.headquarters_id
        token['sub_headquarters_id'] = user.sub_headquarters_id
        return token


class MeSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'phone',
            'role', 'role_display', 'headquarters', 'sub_headquarters',
            'is_active', 'date_joined',
        ]
        read_only_fields = fields
