from accounts.models import Role
from common.permissions import RoleBasedCRUDPermission


class DoctorPermission(RoleBasedCRUDPermission):
    """
    Per §4: Super Admin/HQ Admin/HQ Staff/Sub HQ Staff full CRUD within their
    scope (queryset scoping restricts *which* rows); MR is read-only, further
    scoped in the queryset to only their own assigned Doctors.
    """
    read_roles = (Role.SUPER_ADMIN, Role.HQ_ADMIN, Role.HQ_STAFF, Role.SUB_HQ_STAFF, Role.MR)
    write_roles = (Role.SUPER_ADMIN, Role.HQ_ADMIN, Role.HQ_STAFF, Role.SUB_HQ_STAFF)
