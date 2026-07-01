from django.db.models import Q
from django.utils import timezone

from accounts.models import Role, User
from doctors.models import Doctor
from organizations.models import Headquarters, SubHeadquarters
from visits.models import Visit, VisitStatus


def _doctors_for_user(user):
    if user.role == Role.SUPER_ADMIN:
        return Doctor.objects.all()
    if user.role == Role.HQ_ADMIN:
        return Doctor.objects.filter(
            Q(headquarters_id=user.headquarters_id) | Q(sub_headquarters__headquarters_id=user.headquarters_id)
        )
    if user.role == Role.HQ_STAFF:
        return Doctor.objects.filter(headquarters_id=user.headquarters_id)
    if user.role == Role.SUB_HQ_STAFF:
        return Doctor.objects.filter(sub_headquarters_id=user.sub_headquarters_id)
    if user.role == Role.MR:
        return Doctor.objects.filter(assigned_mr_id=user.id)
    return Doctor.objects.none()


def _mrs_for_user(user):
    mrs = User.objects.filter(role=Role.MR)
    if user.role == Role.SUPER_ADMIN:
        return mrs
    if user.role == Role.HQ_ADMIN:
        return mrs.filter(
            Q(headquarters_id=user.headquarters_id) | Q(sub_headquarters__headquarters_id=user.headquarters_id)
        )
    if user.role == Role.HQ_STAFF:
        return mrs.filter(headquarters_id=user.headquarters_id)
    if user.role == Role.SUB_HQ_STAFF:
        return mrs.filter(sub_headquarters_id=user.sub_headquarters_id)
    if user.role == Role.MR:
        return mrs.filter(pk=user.pk)
    return mrs.none()


def _visits_for_user(user):
    if user.role == Role.SUPER_ADMIN:
        return Visit.objects.all()
    if user.role == Role.HQ_ADMIN:
        return Visit.objects.filter(
            Q(doctor__headquarters_id=user.headquarters_id)
            | Q(doctor__sub_headquarters__headquarters_id=user.headquarters_id)
        )
    if user.role == Role.HQ_STAFF:
        return Visit.objects.filter(doctor__headquarters_id=user.headquarters_id)
    if user.role == Role.SUB_HQ_STAFF:
        return Visit.objects.filter(doctor__sub_headquarters_id=user.sub_headquarters_id)
    if user.role == Role.MR:
        return Visit.objects.filter(mr_id=user.id)
    return Visit.objects.none()


def get_dashboard_summary(user):
    """
    Returns the dashboard summary metrics, scoped to the requesting user's
    role and position in the hierarchy.
    """
    if user.role == Role.SUPER_ADMIN:
        total_headquarters = Headquarters.objects.count()
        total_sub_headquarters = SubHeadquarters.objects.count()
    elif user.role in (Role.HQ_ADMIN, Role.HQ_STAFF):
        total_headquarters = 1 if user.headquarters_id else 0
        total_sub_headquarters = SubHeadquarters.objects.filter(headquarters_id=user.headquarters_id).count()
    elif user.role == Role.SUB_HQ_STAFF:
        total_headquarters = 0
        total_sub_headquarters = 1 if user.sub_headquarters_id else 0
    else:  # MR
        total_headquarters = 0
        total_sub_headquarters = 0

    visit_qs = _visits_for_user(user)
    today = timezone.localdate()

    return {
        'total_headquarters': total_headquarters,
        'total_sub_headquarters': total_sub_headquarters,
        'total_doctors': _doctors_for_user(user).count(),
        'total_mrs': _mrs_for_user(user).count(),
        'todays_visits': visit_qs.filter(visit_date=today).count(),
        'completed_visits': visit_qs.filter(status=VisitStatus.COMPLETED).count(),
        'pending_visits': visit_qs.filter(status=VisitStatus.PENDING).count(),
    }
