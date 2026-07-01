from accounts.models import Role
from common.permissions import RoleBasedCRUDPermission


class UserPermission(RoleBasedCRUDPermission):
    """
    Only Super Admin (all users) and HQ Admin (own Headquarters' HQ Staff,
    Sub HQ Staff, and MRs, enforced via queryset scoping + serializer
    validation) manage user accounts per the assessment's role definitions.
    """
    read_roles = (Role.SUPER_ADMIN, Role.HQ_ADMIN)
    write_roles = (Role.SUPER_ADMIN, Role.HQ_ADMIN)
