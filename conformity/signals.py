from django.db.models.signals import m2m_changed, pre_save, post_save
from django.dispatch import receiver
from .models import (
    Action, Conformity, Control, ControlPoint, DocumentEvidence, Evidence,
    Finding, FindingEvidence, HumanEvidence, Indicator, IndicatorPoint,
    ManualEvidence, Requirement,
)


@receiver(post_save, sender=Control)
def control_post_save_bootstrap(instance: Control, **kwargs):
    Control.controlpoint_bootstrap(instance)

@receiver(pre_save, sender=ControlPoint)
def controlpoint_pre_save_status(sender, instance: ControlPoint, **kwargs):
    ControlPoint.update_status(instance)

@receiver(pre_save, sender=Requirement)
def requirement_pre_save_naming(instance, **kwargs):
    """This function keep hierarchy of the Requirement working on each Requirement instantiation"""
    from .services.requirements import compute_hierarchy_fields
    compute_hierarchy_fields(instance)

@receiver(post_save, sender=Action)
def action_post_save_sync_findings(instance: Action, **kwargs):
    """
    When an Action is saved (status/active may have changed),
    re-evaluate the archive state of all linked Findings.
    """
    for f in instance.associated_findings.all():
        f.update_archived()

@receiver(m2m_changed, sender=Action.associated_findings.through)
def action_finding_sync_on_m2m(instance, action, reverse, pk_set, **kwargs):
    """
    Keep Finding.archived consistent when Action<->Finding links change.

    - reverse=False: `instance` is an Action; `pk_set` are Finding IDs added/removed.
    - reverse=True:  `instance` is a Finding; re-evaluate that single Finding.
    """
    if action not in {'post_add', 'post_remove', 'post_clear'}:
        return

    if reverse:
        findings = [instance]
    else:
        findings = Finding.objects.filter(pk__in=pk_set) if pk_set else instance.associated_findings.all()

    for f in findings:
        f.update_archived()

@receiver(post_save, sender=Action)
def action_post_save_sync(instance: Action, **kwargs):
    """Preserve the existing Action-driven conformity compatibility behavior."""
    for conformity in instance.associated_conformity.all():
        if instance.is_in_progress():
            conformity.set_status_from(0, Conformity.StatusJustification.ACTION)
        elif instance.is_completed():
            conformity.set_status_from(100, Conformity.StatusJustification.ACTION)


@receiver(post_save, sender=Indicator)
def indicator_post_save_bootstrap(instance: Indicator, **kwargs):
    instance.indicator_point_init()


@receiver(pre_save, sender=IndicatorPoint)
def indicatorpoint_pre_save_status(instance: IndicatorPoint, **kwargs):
    instance.status_update()


@receiver(post_save, sender=ControlPoint)
def controlpoint_post_save_evidence(instance: ControlPoint, **kwargs):
    """A ControlPoint is itself Evidence; attach configured targets and evaluate them."""
    if instance.control_id and not instance.conformities.exists():
        conformities = Conformity.objects.filter(
            requirement__in=instance.control.requirements.all(),
        )
        if instance.control.organization_id:
            conformities = conformities.filter(
                organization_id=instance.control.organization_id
            )
        instance.conformities.set(conformities)
    from .services.evidence import evaluate_evidence
    evaluate_evidence(instance)


@receiver(post_save, sender=IndicatorPoint)
def indicatorpoint_post_save_evidence(instance: IndicatorPoint, **kwargs):
    """An IndicatorPoint is itself Evidence; attach configured targets and evaluate them."""
    if instance.indicator_id and not instance.conformities.exists():
        conformities = Conformity.objects.filter(
            requirement__in=instance.indicator.requirements.all(),
        )
        if instance.indicator.organization_id:
            conformities = conformities.filter(
                organization_id=instance.indicator.organization_id
            )
        instance.conformities.set(conformities)
    from .services.evidence import evaluate_evidence
    evaluate_evidence(instance)


@receiver(m2m_changed, sender=Control.requirements.through)
def control_requirement_targets_changed(instance, action, **kwargs):
    if action in {'post_add', 'post_remove', 'post_clear'}:
        conformities = Conformity.objects.filter(
            requirement__in=instance.requirements.all(),
        )
        if instance.organization_id:
            conformities = conformities.filter(
                organization_id=instance.organization_id
            )
        for point in instance.get_controlpoint():
            point.conformities.set(conformities)


@receiver(m2m_changed, sender=Indicator.requirements.through)
def indicator_requirement_targets_changed(instance, action, **kwargs):
    if action in {'post_add', 'post_remove', 'post_clear'}:
        conformities = Conformity.objects.filter(
            requirement__in=instance.requirements.all(),
        )
        if instance.organization_id:
            conformities = conformities.filter(
                organization_id=instance.organization_id
            )
        for point in IndicatorPoint.objects.filter(indicator=instance):
            point.conformities.set(conformities)


@receiver(m2m_changed, sender=Evidence.conformities.through)
def evidence_conformity_changed(instance, action, reverse, pk_set, **kwargs):
    """Recompute both newly-associated and detached Conformities."""
    from .services.evidence import evaluate_conformity, evaluate_evidence

    if action == 'pre_clear':
        if reverse:
            instance._cleared_evidence_ids = list(
                instance.evidence.values_list('pk', flat=True)
            )
        else:
            instance._cleared_conformity_ids = list(
                instance.conformities.values_list('pk', flat=True)
            )
        return

    if action not in {'post_add', 'post_remove', 'post_clear'}:
        return

    if reverse:
        evidence_ids = pk_set or getattr(instance, '_cleared_evidence_ids', [])
        if action == 'post_add':
            # Every added Evidence is a real trigger, including an old Evidence
            # attached to this Conformity only now.
            for evidence in Evidence.objects.filter(pk__in=evidence_ids):
                evaluate_conformity(instance, trigger=evidence)
        else:
            evaluate_conformity(instance)
        if hasattr(instance, '_cleared_evidence_ids'):
            del instance._cleared_evidence_ids
        return

    if action == 'post_add':
        evaluate_evidence(instance)
    else:
        removed_ids = pk_set or getattr(instance, '_cleared_conformity_ids', [])
        evaluate_evidence(instance)
        for conformity in Conformity.objects.filter(pk__in=removed_ids):
            evaluate_conformity(conformity)

    if hasattr(instance, '_cleared_conformity_ids'):
        del instance._cleared_conformity_ids


@receiver(post_save, sender=HumanEvidence)
@receiver(post_save, sender=ManualEvidence)
@receiver(post_save, sender=DocumentEvidence)
@receiver(post_save, sender=FindingEvidence)
def specialized_evidence_saved(instance, **kwargs):
    from .services.evidence import evaluate_evidence
    evaluate_evidence(instance)


@receiver(post_save, sender=Evidence)
def evidence_saved(instance: Evidence, **kwargs):
    from .services.evidence import evaluate_evidence
    evaluate_evidence(instance)

