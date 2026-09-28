from django.db.models.signals import m2m_changed, pre_save, post_save
from django.dispatch import receiver
from .models import Requirement, Control, ControlPoint, Action, Finding, Conformity, \
    Indicator, IndicatorPoint, Evidence, HumanEvidence, ManualEvidence,
    DocumentEvidence, FindingEvidence


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

@receiver(post_save, sender=ControlPoint)
def controlpoint_post_save_evidence(instance: ControlPoint, **kwargs):
    """A ControlPoint is itself Evidence; attach configured targets and evaluate them."""
    if instance.control_id and not instance.conformities.exists():
        conformities = Conformity.objects.filter(
            organization=instance.control.organization,
            requirement__in=instance.control.requirements.all(),
        )
        instance.conformities.set(conformities)
    from .services.evidence import evaluate_evidence
    evaluate_evidence(instance)


@receiver(post_save, sender=IndicatorPoint)
def indicatorpoint_post_save_evidence(instance: IndicatorPoint, **kwargs):
    """An IndicatorPoint is itself Evidence; attach configured targets and evaluate them."""
    if instance.indicator_id and not instance.conformities.exists():
        conformities = Conformity.objects.filter(
            organization=instance.indicator.organization,
            requirement__in=instance.indicator.requirements.all(),
        )
        instance.conformities.set(conformities)
    from .services.evidence import evaluate_evidence
    evaluate_evidence(instance)


@receiver(m2m_changed, sender=Control.requirements.through)
def control_requirement_targets_changed(instance, action, **kwargs):
    if action in {'post_add', 'post_remove', 'post_clear'}:
        conformities = Conformity.objects.filter(
            organization=instance.organization,
            requirement__in=instance.requirements.all(),
        )
        for point in instance.get_controlpoint():
            point.conformities.set(conformities)


@receiver(m2m_changed, sender=Indicator.requirements.through)
def indicator_requirement_targets_changed(instance, action, **kwargs):
    if action in {'post_add', 'post_remove', 'post_clear'}:
        conformities = Conformity.objects.filter(
            organization=instance.organization,
            requirement__in=instance.requirements.all(),
        )
        for point in IndicatorPoint.objects.filter(indicator=instance):
            point.conformities.set(conformities)


@receiver(m2m_changed, sender=Evidence.conformities.through)
def evidence_conformity_changed(instance, action, reverse, pk_set, **kwargs):
    if action == 'pre_clear' and not reverse:
        instance._cleared_conformity_ids = list(
            instance.conformities.values_list('pk', flat=True)
        )
        return
    if action not in {'post_add', 'post_remove', 'post_clear'}:
        return
    from .services.evidence import evaluate_evidence
    if reverse:
        instance.evaluate_evidence()
    else:
        evaluate_evidence(instance)
        removed_ids = pk_set or getattr(instance, '_cleared_conformity_ids', [])
        if action in {'post_remove', 'post_clear'} and removed_ids:
            for conformity in Conformity.objects.filter(pk__in=removed_ids):
                conformity.evaluate_evidence()
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

