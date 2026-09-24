"""Audit business M2M relations, including reverse edits and exact removals."""
from functools import partial

from auditlog.context import auditlog_disabled
from auditlog.models import LogEntry
from django.db.models.signals import m2m_changed


def log_relation_changes(sender, instance, action, reverse, pk_set, using, *, field, **kwargs):
    if auditlog_disabled.get() or action not in {'post_add', 'pre_remove', 'pre_clear'}:
        return
    operation = 'add' if action == 'post_add' else 'delete'
    manager = LogEntry.objects.db_manager(using)
    if reverse:
        owners = field.model.objects.using(using)
        if action != 'post_add':
            owners = owners.filter(**{field.name: instance})
        if pk_set is not None:
            owners = owners.filter(pk__in=pk_set)
        for owner in owners:
            manager.log_m2m_changes([instance], owner, operation, field.name)
    else:
        related = field.remote_field.model.objects.using(using)
        if action != 'post_add':
            # Capture only existing links, before Django removes them. The M2M
            # manager wraps this signal and the deletion in the same transaction.
            related = getattr(instance, field.name).using(using).all()
        if pk_set is not None:
            related = related.filter(pk__in=pk_set)
        related = list(related)
        manager.log_m2m_changes(related, instance, operation, field.name)
        if field.remote_field.symmetrical:
            for other in related:
                if other.pk != instance.pk:
                    manager.log_m2m_changes([instance], other, operation, field.name)


def register_m2m_audit(models):
    for model in models:
        for field in model._meta.local_many_to_many:
            m2m_changed.connect(
                partial(log_relation_changes, field=field),
                sender=field.remote_field.through,
                dispatch_uid=f'conformity.audit.{model._meta.label}.{field.name}',
                weak=False,
            )
