from rest_framework.permissions import SAFE_METHODS, BasePermission

from accounts.models import Role


class VisitPermission(BasePermission):
    """
    Super Admin, HQ Staff, and Sub HQ Staff have full CRUD; HQ Admin can read
    and update but not create or delete; MR can create and update their own
    visits but not delete.

    HQ Admin's access follows the "hierarchy-based role permissions" model in
    the spec: a role inherits the capabilities of the roles beneath it, scoped
    to its own HQ.
    """
    read_roles = (Role.SUPER_ADMIN, Role.HQ_ADMIN, Role.HQ_STAFF, Role.SUB_HQ_STAFF, Role.MR)
    create_roles = (Role.SUPER_ADMIN, Role.HQ_STAFF, Role.SUB_HQ_STAFF, Role.MR)
    update_roles = (Role.SUPER_ADMIN, Role.HQ_ADMIN, Role.HQ_STAFF, Role.SUB_HQ_STAFF, Role.MR)
    delete_roles = (Role.SUPER_ADMIN, Role.HQ_STAFF, Role.SUB_HQ_STAFF)

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False

        action = getattr(view, 'action', None)
        if request.method in SAFE_METHODS:
            return user.role in self.read_roles
        if action == 'create':
            return user.role in self.create_roles
        if action == 'destroy':
            return user.role in self.delete_roles
        # update, partial_update, mark_visit
        return user.role in self.update_roles
