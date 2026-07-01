from rest_framework import serializers

from accounts.models import Role

from .models import Headquarters, SubHeadquarters


class HeadquartersSerializer(serializers.ModelSerializer):
    class Meta:
        model = Headquarters
        fields = [
            'id', 'name', 'code', 'address', 'city', 'state', 'is_active',
            'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']


class SubHeadquartersSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubHeadquarters
        fields = [
            'id', 'headquarters', 'name', 'code', 'address', 'is_active',
            'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

    def validate_headquarters(self, headquarters):
        user = self.context['request'].user
        if user.role == Role.HQ_ADMIN and headquarters.id != user.headquarters_id:
            raise serializers.ValidationError(
                'HQ Admin can only manage Sub Headquarters under their own Headquarters.'
            )
        return headquarters
