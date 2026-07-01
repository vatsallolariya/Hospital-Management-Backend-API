from accounts.models import Role
from common.permissions import RoleBasedCRUDPermission


class HeadquartersPermission(RoleBasedCRUDPermission):
    """Per §4: Super Admin full CRUD; HQ Admin/HQ Staff read own only."""
    read_roles = (Role.SUPER_ADMIN, Role.HQ_ADMIN, Role.HQ_STAFF)
    write_roles = (Role.SUPER_ADMIN,)


class SubHeadquartersPermission(RoleBasedCRUDPermission):
    """
    Per §4: Super Admin full CRUD (all); HQ Admin full CRUD (own HQ, enforced
    via queryset scoping + serializer validation); HQ Staff/Sub HQ Staff read
    only within their scope.
    """
    read_roles = (Role.SUPER_ADMIN, Role.HQ_ADMIN, Role.HQ_STAFF, Role.SUB_HQ_STAFF)
    write_roles = (Role.SUPER_ADMIN, Role.HQ_ADMIN)
