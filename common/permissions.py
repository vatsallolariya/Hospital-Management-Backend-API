from rest_framework.permissions import SAFE_METHODS, BasePermission


class RoleBasedCRUDPermission(BasePermission):
    """
    Per-method role gate: `read_roles` may use safe methods (GET/HEAD/
    OPTIONS), `write_roles` may use the rest (POST/PUT/PATCH/DELETE).
    Gates the verb only; combine with queryset scoping to restrict rows.
    """
    read_roles: tuple = ()
    write_roles: tuple = ()

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        allowed_roles = self.read_roles if request.method in SAFE_METHODS else self.write_roles
        return user.role in allowed_roles
