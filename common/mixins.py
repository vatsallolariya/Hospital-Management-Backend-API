import logging

from django.db.models import Q

from accounts.models import Role


class AuditLogMixin:
    """
    Logs CRUD actions and permission denials for a view, using the per-app
    logger. Writes and denials log at INFO/WARNING; reads log at DEBUG.

    Note: `perform_create` is not overridden here. ViewSets that override it
    to stamp `created_by` should log the create explicitly with
    `self.audit_logger.info(...)`.
    """

    @property
    def audit_logger(self):
        return logging.getLogger(self.__class__.__module__.split('.')[0])

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        self.audit_logger.debug('Listed %s by user=%s', self.get_queryset().model.__name__, request.user)
        return response

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        self.audit_logger.debug(
            'Retrieved %s id=%s by user=%s', self.get_queryset().model.__name__, kwargs.get('pk'), request.user,
        )
        return response

    def perform_update(self, serializer):
        super().perform_update(serializer)
        self.audit_logger.info(
            'Updated %s id=%s by user=%s',
            serializer.instance.__class__.__name__, serializer.instance.pk, self.request.user,
        )

    def perform_destroy(self, instance):
        model_name = instance.__class__.__name__
        pk = instance.pk
        super().perform_destroy(instance)
        self.audit_logger.info('Deleted %s id=%s by user=%s', model_name, pk, self.request.user)

    def permission_denied(self, request, message=None, code=None):
        self.audit_logger.warning(
            'Permission denied: user=%s action=%s view=%s',
            request.user, getattr(self, 'action', request.method), self.__class__.__name__,
        )
        super().permission_denied(request, message=message, code=code)


class HierarchyScopedQuerysetMixin:
    """
    Restricts a ViewSet's queryset to the rows the requesting user's role may
    see:

        Super Admin    -> everything
        HQ Admin       -> own Headquarters + that HQ's Sub Headquarters
        HQ Staff       -> own Headquarters only
        Sub HQ Staff   -> own Sub Headquarters only
        MR             -> own Headquarters or Sub Headquarters (override
                          `scope_queryset_to_mr` to limit further)

    Set `hq_lookup_field` / `sub_hq_lookup_field` to the model's lookup paths
    (e.g. 'headquarters' or 'doctor__headquarters'), or None if the model has
    no such relation.
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
        Default MR scoping: rows in the MR's own Headquarters or Sub
        Headquarters. Override to limit an MR to only their own rows.
        """
        if user.headquarters_id and self.hq_lookup_field:
            return qs.filter(**{f'{self.hq_lookup_field}_id': user.headquarters_id})
        if user.sub_headquarters_id and self.sub_hq_lookup_field:
            return qs.filter(**{f'{self.sub_hq_lookup_field}_id': user.sub_headquarters_id})
        return qs.none()
