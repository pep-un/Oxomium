"""Audit literal bulk updates without re-running business save signals."""
from copy import copy

from auditlog.context import auditlog_disabled
from auditlog.diff import model_instance_diff
from auditlog.models import LogEntry
from django.conf import settings
from django.db import transaction


def update_with_audit(queryset, **changes):
    """Update and record each actual diff atomically; values must be literals."""
    with transaction.atomic(using=queryset.db):
        instances = list(queryset.select_for_update())
        if not instances:
            return 0
        count = queryset.model.objects.using(queryset.db).filter(
            pk__in=[instance.pk for instance in instances]
        ).update(**changes)
        if not auditlog_disabled.get():
            for previous in instances:
                current = copy(previous)
                current._state = copy(previous._state)
                current._state.fields_cache = previous._state.fields_cache.copy()
                for field, value in changes.items():
                    setattr(current, field, value)
                diff = model_instance_diff(
                    previous, current, fields_to_check=changes,
                    use_json_for_changes=settings.AUDITLOG_STORE_JSON_CHANGES,
                )
                if diff:
                    LogEntry.objects.db_manager(queryset.db).log_create(
                        current, action=LogEntry.Action.UPDATE, changes=diff,
                    )
        return count
