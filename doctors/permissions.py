from accounts.models import Role
from common.permissions import RoleBasedCRUDPermission


class DoctorPermission(RoleBasedCRUDPermission):
    """
    Super Admin, HQ Admin, HQ Staff, and Sub HQ Staff have full CRUD within
    their scope; MR is read-only and limited to their own assigned Doctors.

    HQ Admin's write access follows the "hierarchy-based role permissions"
    model in the spec: a role inherits the capabilities of the roles beneath
    it, so HQ Admin can do anything its HQ Staff can, scoped to its own HQ.
    """
    read_roles = (Role.SUPER_ADMIN, Role.HQ_ADMIN, Role.HQ_STAFF, Role.SUB_HQ_STAFF, Role.MR)
    write_roles = (Role.SUPER_ADMIN, Role.HQ_ADMIN, Role.HQ_STAFF, Role.SUB_HQ_STAFF)
