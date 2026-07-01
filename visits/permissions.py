from rest_framework.permissions import SAFE_METHODS, BasePermission

from accounts.models import Role


class VisitPermission(BasePermission):
    """
    Per §4: Super Admin has full CRUD (all); HQ Staff/Sub HQ Staff have full
    CRUD within their own HQ/Sub HQ; HQ Admin can read and manage (update,
    including mark-visit) within their own HQ but not create/delete; MR can
    create/update only their own visits (mark-visit, submit report), never
    delete. Queryset scoping restricts *which* rows are visible/editable —
    this class only gates the action.
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
