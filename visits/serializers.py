from rest_framework import serializers

from accounts.models import Role

from .models import Visit, VisitStatus


class VisitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Visit
        fields = [
            'id', 'doctor', 'mr', 'visit_date', 'status', 'check_in_time',
            'purpose', 'remarks', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'check_in_time', 'created_at', 'updated_at']
        extra_kwargs = {'mr': {'required': False}}

    def validate_status(self, value):
        if self.instance is None:
            return value

        current = self.instance.status
        if current != VisitStatus.PENDING and value != current:
            raise serializers.ValidationError(f'Cannot change status of a {current.lower()} visit.')
        if current == VisitStatus.PENDING and value == VisitStatus.COMPLETED:
            raise serializers.ValidationError('Use the mark-visit action to complete a visit.')
        return value

    def validate(self, attrs):
        doctor = attrs.get('doctor', getattr(self.instance, 'doctor', None))
        mr = attrs.get('mr', getattr(self.instance, 'mr', None))
        user = self.context['request'].user

        if user.role == Role.MR:
            attrs['mr'] = user
            if not doctor or doctor.assigned_mr_id != user.id:
                raise serializers.ValidationError(
                    {'doctor': 'MR can only log Visits for their own assigned Doctors.'}
                )
            return attrs

        if mr is None:
            raise serializers.ValidationError({'mr': 'This field is required.'})
        if mr.role != Role.MR:
            raise serializers.ValidationError({'mr': 'mr must be a user with role MR.'})

        if doctor is not None:
            if doctor.headquarters_id and mr.headquarters_id != doctor.headquarters_id:
                raise serializers.ValidationError(
                    {'mr': 'mr must belong to the same Headquarters as the Doctor.'}
                )
            if doctor.sub_headquarters_id and mr.sub_headquarters_id != doctor.sub_headquarters_id:
                raise serializers.ValidationError(
                    {'mr': 'mr must belong to the same Sub Headquarters as the Doctor.'}
                )

        if user.role == Role.HQ_STAFF:
            if not doctor or doctor.headquarters_id != user.headquarters_id:
                raise serializers.ValidationError(
                    {'doctor': 'HQ Staff can only manage Visits for Doctors under their own Headquarters.'}
                )
        elif user.role == Role.HQ_ADMIN:
            owning_hq_id = doctor.headquarters_id if doctor and doctor.headquarters_id else (
                doctor.sub_headquarters.headquarters_id if doctor and doctor.sub_headquarters_id else None
            )
            if owning_hq_id != user.headquarters_id:
                raise serializers.ValidationError(
                    {'doctor': 'HQ Admin can only manage Visits for Doctors under their own Headquarters.'}
                )
        elif user.role == Role.SUB_HQ_STAFF:
            if not doctor or doctor.sub_headquarters_id != user.sub_headquarters_id:
                raise serializers.ValidationError(
                    {'doctor': 'Sub HQ Staff can only manage Visits for Doctors under their own Sub Headquarters.'}
                )

        return attrs
