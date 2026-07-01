from accounts.models import Role
from common.permissions import RoleBasedCRUDPermission


class HeadquartersPermission(RoleBasedCRUDPermission):
    """Super Admin has full CRUD; HQ Admin and HQ Staff can read their own."""
    read_roles = (Role.SUPER_ADMIN, Role.HQ_ADMIN, Role.HQ_STAFF)
    write_roles = (Role.SUPER_ADMIN,)


class SubHeadquartersPermission(RoleBasedCRUDPermission):
    """
    Super Admin has full CRUD; HQ Admin has full CRUD within their own
    Headquarters; HQ Staff and Sub HQ Staff can read within their scope.
    """
    read_roles = (Role.SUPER_ADMIN, Role.HQ_ADMIN, Role.HQ_STAFF, Role.SUB_HQ_STAFF)
    write_roles = (Role.SUPER_ADMIN, Role.HQ_ADMIN)
