from django.db import models, transaction
from django.utils import timezone
from auditlog.models import LogEntry


def ensure_for_framework(organization, framework):
    """Create missing assessments without resetting assessments already entered."""
    from conformity.models import Conformity, Requirement

    requirement_ids = Requirement.objects.filter(framework=framework).values_list('pk', flat=True)
    with transaction.atomic():
        for requirement_id in requirement_ids:
            # Emit post_save only for genuinely new assessments.
            Conformity.objects.get_or_create(
                organization=organization, requirement_id=requirement_id,
            )


def remove_for_framework(organization, framework):
    from conformity.models import Conformity

    with transaction.atomic():
        Conformity.objects.filter(
            organization=organization, requirement__framework=framework
        ).delete()


def apply_framework(organization, framework):
    """Apply one framework and create only missing assessments."""
    from conformity.models import Framework, Organization

    framework_id = getattr(framework, 'pk', framework)
    through = Organization.applicable_frameworks.through
    with transaction.atomic():
        _, created = through.objects.get_or_create(
            organization_id=organization.pk, framework_id=framework_id
        )
        ensure_for_framework(organization, framework_id)
        if created:
            LogEntry.objects.log_m2m_changes(
                Framework.objects.filter(pk=framework_id), organization,
                'add', 'applicable_frameworks',
            )


def unapply_framework(organization, framework):
    """Remove a framework and its assessments as a single operation."""
    from conformity.models import Framework, Organization

    framework_id = getattr(framework, 'pk', framework)
    through = Organization.applicable_frameworks.through
    with transaction.atomic():
        removed, _ = through.objects.filter(
            organization_id=organization.pk, framework_id=framework_id
        ).delete()
        remove_for_framework(organization, framework_id)
        if removed:
            LogEntry.objects.log_m2m_changes(
                Framework.objects.filter(pk=framework_id), organization,
                'delete', 'applicable_frameworks',
            )


def set_frameworks(organization, frameworks):
    """Reconcile an organization's selection without resetting existing answers."""
    desired = {getattr(framework, 'pk', framework) for framework in frameworks}
    with transaction.atomic():
        current = set(
            organization.applicable_frameworks.values_list('pk', flat=True)
        )
        for framework_id in current - desired:
            unapply_framework(organization, framework_id)
        for framework_id in desired - current:
            apply_framework(organization, framework_id)
        # Repair missing assessments on pre-existing links, without overwriting answers.
        for framework_id in current & desired:
            ensure_for_framework(organization, framework_id)


def recompute_parent_chain(conformity):
    """Aggregate this node and its ancestors, one level at a time."""
    from conformity.models import Conformity

    with transaction.atomic():
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
