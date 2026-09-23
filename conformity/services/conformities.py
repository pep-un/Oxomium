from django.db import models, transaction
from django.utils import timezone
from auditlog.context import set_actor


def ensure_for_framework(organization, framework):
    """Create missing assessments without resetting assessments already entered."""
    from conformity.models import Conformity, Requirement

    requirement_ids = Requirement.objects.filter(framework=framework).values_list('pk', flat=True)
    with transaction.atomic(), set_actor('system'):
        Conformity.objects.bulk_create(
            [Conformity(organization=organization, requirement_id=pk) for pk in requirement_ids],
            ignore_conflicts=True,
        )


def remove_for_framework(organization, framework):
    from conformity.models import Conformity

    with transaction.atomic(), set_actor('system'):
        Conformity.objects.filter(
            organization=organization, requirement__framework=framework
        ).delete()


def recompute_parent_chain(conformity):
    """Aggregate this node and its ancestors, one level at a time."""
    from conformity.models import Conformity

    with transaction.atomic(), set_actor('system'):
        current = conformity
        while current is not None:
            mean = Conformity.objects.filter(
                organization=current.organization,
                requirement__parent=current.requirement,
                applicable=True,
                status__range=(0, 100),
            ).aggregate(mean=models.Avg('status'))['mean']
            if mean is not None:
                current.status = mean
                current.status_justification = Conformity.StatusJustification.CONFORMITY
                current.status_last_update = timezone.now()
                current.save(update_fields=['status', 'status_justification', 'status_last_update'])
            current = current.get_parent()


def propagate_applicable_and_comment(root, applicable, comment=None):
    """Apply explicit edits to descendants; re-enable ancestors when needed."""
    from conformity.models import Conformity

    with transaction.atomic():
        if not root.requirement.is_leaf_node() and (not applicable or comment is not None):
            changes = {'applicable': applicable}
            if comment is not None:
                changes['comment'] = comment
            Conformity.objects.filter(
                organization=root.organization,
                requirement__in=root.requirement.get_descendants(),
            ).update(**changes)
        if applicable and root.requirement.is_child_node():
            Conformity.objects.filter(
                organization=root.organization,
                requirement__in=root.requirement.get_ancestors(),
            ).update(applicable=True)
