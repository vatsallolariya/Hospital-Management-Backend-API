from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Role, User


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


class UserSerializer(serializers.ModelSerializer):
    """
    Create/manage User accounts. Only reachable by Super Admin and HQ Admin
    (see accounts.permissions.UserPermission) — HQ Admin is further
    restricted here to subordinate roles under their own Headquarters.
    """
    password = serializers.CharField(write_only=True, required=False, min_length=8)
    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'email', 'password', 'first_name', 'last_name', 'phone',
            'role', 'role_display', 'headquarters', 'sub_headquarters',
            'is_active', 'created_by', 'date_joined', 'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'date_joined', 'updated_at']

    def validate(self, attrs):
        if self.instance is None and not attrs.get('password'):
            raise serializers.ValidationError({'password': 'This field is required.'})

        role = attrs.get('role', getattr(self.instance, 'role', None))
        headquarters = attrs.get('headquarters', getattr(self.instance, 'headquarters', None))
        sub_headquarters = attrs.get('sub_headquarters', getattr(self.instance, 'sub_headquarters', None))

        if role == Role.SUPER_ADMIN:
            if headquarters or sub_headquarters:
                raise serializers.ValidationError('Super Admin must not be scoped to a Headquarters or Sub Headquarters.')
        elif role in (Role.HQ_ADMIN, Role.HQ_STAFF):
            if not headquarters:
                raise serializers.ValidationError(f'{Role(role).label} requires a Headquarters.')
            if sub_headquarters:
                raise serializers.ValidationError(f'{Role(role).label} must not have a Sub Headquarters.')
        elif role == Role.SUB_HQ_STAFF:
            if not sub_headquarters:
                raise serializers.ValidationError('Sub HQ Staff requires a Sub Headquarters.')
            if headquarters:
                raise serializers.ValidationError('Sub HQ Staff must not have a Headquarters.')
        elif role == Role.MR:
            if bool(headquarters) == bool(sub_headquarters):
                raise serializers.ValidationError('Medical Rep requires exactly one of Headquarters or Sub Headquarters.')

        requester = self.context['request'].user
        if requester.role == Role.HQ_ADMIN:
            if role not in (Role.HQ_STAFF, Role.SUB_HQ_STAFF, Role.MR):
                raise serializers.ValidationError(
                    {'role': 'HQ Admin can only create or manage HQ Staff, Sub HQ Staff, or MR accounts.'}
                )
            owning_hq_id = headquarters.id if headquarters else sub_headquarters.headquarters_id
            if owning_hq_id != requester.headquarters_id:
                raise serializers.ValidationError('HQ Admin can only manage users under their own Headquarters.')

        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password')
        return User.objects.create_user(password=password, created_by=self.context['request'].user, **validated_data)

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.full_clean(exclude=['password'])
        instance.save()
        return instance
