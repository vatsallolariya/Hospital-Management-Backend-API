from accounts.models import Role
from common.permissions import RoleBasedCRUDPermission


class UserPermission(RoleBasedCRUDPermission):
    """Only Super Admin and HQ Admin can manage user accounts."""
    read_roles = (Role.SUPER_ADMIN, Role.HQ_ADMIN)
    write_roles = (Role.SUPER_ADMIN, Role.HQ_ADMIN)
