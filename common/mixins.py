from django.db.models import Q

from accounts.models import Role


class HierarchyScopedQuerysetMixin:
    """
    Restricts a ViewSet's queryset to the rows the requesting user's role is
    allowed to see, per the hierarchy in IMPLEMENTATION_PLAN.md §3.2/§4:

        Super Admin    -> everything
        HQ Admin       -> own Headquarters + that HQ's Sub Headquarters
        HQ Staff       -> own Headquarters only
        Sub HQ Staff   -> own Sub Headquarters only
        MR             -> own Headquarters or Sub Headquarters (override
                           `scope_queryset_to_mr` where an MR should instead
                           be limited to only their own rows, e.g. Doctor.assigned_mr
                           or Visit.mr)

    Intended for models that reference a Headquarters/SubHeadquarters via FK
    (Doctor, Visit, SubHeadquarters, User, ...). For the Headquarters model
    itself, "own HQ" scoping is just `qs.filter(pk=user.headquarters_id)` —
    override `get_queryset()` directly in that ViewSet instead of using this
    mixin.

    Configure via class attributes on the ViewSet, using Django `__` lookup
    paths relative to the model:

        hq_lookup_field = 'headquarters'              # Doctor
        sub_hq_lookup_field = 'sub_headquarters'       # Doctor
        hq_lookup_field = 'doctor__headquarters'       # Visit
        sub_hq_lookup_field = 'doctor__sub_headquarters'  # Visit

    Set a field to None if the model has no such relation.
    """

    hq_lookup_field = 'headquarters'
    sub_hq_lookup_field = 'sub_headquarters'

    def get_queryset(self):
        qs = super().get_queryset()
        return self.scope_queryset_to_user(qs, self.request.user)

    def scope_queryset_to_user(self, qs, user):
        role = user.role

        if role == Role.SUPER_ADMIN:
            return qs

        if role in (Role.HQ_ADMIN, Role.HQ_STAFF):
            if not self.hq_lookup_field:
                return qs.none()
            filters = Q(**{f'{self.hq_lookup_field}_id': user.headquarters_id})
            if role == Role.HQ_ADMIN and self.sub_hq_lookup_field:
                filters |= Q(**{f'{self.sub_hq_lookup_field}__headquarters_id': user.headquarters_id})
            return qs.filter(filters)

        if role == Role.SUB_HQ_STAFF:
            if not self.sub_hq_lookup_field:
                return qs.none()
            return qs.filter(**{f'{self.sub_hq_lookup_field}_id': user.sub_headquarters_id})

        if role == Role.MR:
            return self.scope_queryset_to_mr(qs, user)

        return qs.none()

    def scope_queryset_to_mr(self, qs, user):
        """
        Default MR scoping: rows in the MR's own Headquarters or Sub Headquarters.
        Modules where an MR must see only rows tied to them personally (e.g.
        Doctor.assigned_mr, Visit.mr) should override this method rather than
        relying on the HQ/Sub HQ-wide default.
        """
        if user.headquarters_id and self.hq_lookup_field:
            return qs.filter(**{f'{self.hq_lookup_field}_id': user.headquarters_id})
        if user.sub_headquarters_id and self.sub_hq_lookup_field:
            return qs.filter(**{f'{self.sub_hq_lookup_field}_id': user.sub_headquarters_id})
        return qs.none()
