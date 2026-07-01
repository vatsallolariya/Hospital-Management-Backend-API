from rest_framework.permissions import SAFE_METHODS, BasePermission

from accounts.models import Role


class HasRole(BasePermission):
    """
    Base class for role-gated permissions. Subclasses set `allowed_roles`.
    Use `HasRole.for_roles(...)` to build a one-off permission class inline
    for a view that doesn't warrant a named subclass below.
    """
    allowed_roles: tuple = ()

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role in self.allowed_roles)

    @classmethod
    def for_roles(cls, *roles):
        return type('DynamicHasRole', (cls,), {'allowed_roles': tuple(roles)})


class IsSuperAdmin(HasRole):
    allowed_roles = (Role.SUPER_ADMIN,)


class IsHQAdmin(HasRole):
    allowed_roles = (Role.HQ_ADMIN,)


class IsHQStaff(HasRole):
    allowed_roles = (Role.HQ_STAFF,)


class IsSubHQStaff(HasRole):
    allowed_roles = (Role.SUB_HQ_STAFF,)


class IsMR(HasRole):
    allowed_roles = (Role.MR,)


class IsHQAdminOrAbove(HasRole):
    """Super Admin or HQ Admin — e.g. Headquarters/Sub Headquarters write access."""
    allowed_roles = (Role.SUPER_ADMIN, Role.HQ_ADMIN)


class IsHQStaffOrAbove(HasRole):
    """Super Admin, HQ Admin, or HQ Staff — e.g. Doctor write access within an HQ."""
    allowed_roles = (Role.SUPER_ADMIN, Role.HQ_ADMIN, Role.HQ_STAFF)


class IsSubHQStaffOrAbove(HasRole):
    """Super Admin, HQ Admin, or Sub HQ Staff — e.g. Doctor write access within a Sub HQ."""
    allowed_roles = (Role.SUPER_ADMIN, Role.HQ_ADMIN, Role.SUB_HQ_STAFF)


class RoleBasedCRUDPermission(BasePermission):
    """
    Generic per-method role gate: `read_roles` may use safe methods
    (GET/HEAD/OPTIONS), `write_roles` may use unsafe methods (POST/PUT/
    PATCH/DELETE). Subclasses set both tuples. Combine with queryset
    scoping (see `common.mixins.HierarchyScopedQuerysetMixin`) to restrict
    *which* rows are visible/editable — this class only gates the verb.
    """
    read_roles: tuple = ()
    write_roles: tuple = ()

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        allowed_roles = self.read_roles if request.method in SAFE_METHODS else self.write_roles
        return user.role in allowed_roles
