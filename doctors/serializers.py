from rest_framework import serializers

from accounts.models import Role

from .models import Doctor


class DoctorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Doctor
        fields = [
            'id', 'name', 'specialization', 'phone', 'email', 'clinic_name', 'address',
            'headquarters', 'sub_headquarters', 'assigned_mr', 'is_active',
            'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

    def validate(self, attrs):
        headquarters = attrs.get('headquarters', getattr(self.instance, 'headquarters', None))
        sub_headquarters = attrs.get('sub_headquarters', getattr(self.instance, 'sub_headquarters', None))
        assigned_mr = attrs.get('assigned_mr', getattr(self.instance, 'assigned_mr', None))

        if bool(headquarters) == bool(sub_headquarters):
            raise serializers.ValidationError(
                'Doctor requires exactly one of Headquarters or Sub Headquarters.'
            )

        user = self.context['request'].user
        if user.role == Role.HQ_STAFF:
            if not headquarters or headquarters.id != user.headquarters_id:
                raise serializers.ValidationError(
                    'HQ Staff can only manage Doctors under their own Headquarters.'
                )
        elif user.role == Role.HQ_ADMIN:
            owning_hq_id = headquarters.id if headquarters else sub_headquarters.headquarters_id
            if owning_hq_id != user.headquarters_id:
                raise serializers.ValidationError(
                    'HQ Admin can only manage Doctors under their own Headquarters.'
                )
        elif user.role == Role.SUB_HQ_STAFF:
            if not sub_headquarters or sub_headquarters.id != user.sub_headquarters_id:
                raise serializers.ValidationError(
                    'Sub HQ Staff can only manage Doctors under their own Sub Headquarters.'
                )

        if assigned_mr is not None:
            if assigned_mr.role != Role.MR:
                raise serializers.ValidationError(
                    {'assigned_mr': 'assigned_mr must be a user with role MR.'}
                )
            if headquarters and assigned_mr.headquarters_id != headquarters.id:
                raise serializers.ValidationError(
                    {'assigned_mr': 'assigned_mr must belong to the same Headquarters as the Doctor.'}
                )
            if sub_headquarters and assigned_mr.sub_headquarters_id != sub_headquarters.id:
                raise serializers.ValidationError(
                    {'assigned_mr': 'assigned_mr must belong to the same Sub Headquarters as the Doctor.'}
                )

        return attrs
