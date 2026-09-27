from django.db.models.signals import m2m_changed, pre_save, post_save
from django.dispatch import receiver
from .models import Requirement, Control, ControlPoint, Action, Finding, Conformity, \
    Indicator, IndicatorPoint, Evidence, HumanEvidence


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
def controlpoint_post_save_sync(instance: ControlPoint, **kwargs):
    """
    Transactional rule:
      - NONCOMPLIANT (current period) -> conformity = 0 (CTRL)
      - COMPLIANT    (current period) -> try conformity = 100 (CTRL) if no negatives remain
    """
    if instance.is_current_period() and instance.is_final_status():
        for conf in instance.control.conformity.all():
            if instance.status == ControlPoint.Status.NONCOMPLIANT:
                conf.set_status_from(0, Conformity.StatusJustification.CONTROL)
            elif instance.status == ControlPoint.Status.COMPLIANT:
                conf.set_status_from(100, Conformity.StatusJustification.CONTROL)

@receiver(post_save, sender=Action)
def action_post_save_sync(instance: Action, **kwargs):
    """
    Transactional rule:
      - in progress -> conformity = 0 (ACT)
      - ended       -> try conformity = 100 (ACT) if no negatives remain
    """
    for conf in instance.associated_conformity.all():
        if instance.is_in_progress():
            conf.set_status_from(0, Conformity.StatusJustification.ACTION)
        elif instance.is_completed():
            conf.set_status_from(100, Conformity.StatusJustification.ACTION)

@receiver(post_save, sender=Indicator)
def indicator_post_save_bootstrap(instance: Indicator, **kwargs):
    instance.indicator_point_init()

@receiver(pre_save, sender=IndicatorPoint)
def indicatorpoint_pre_save_ctrl(instance: IndicatorPoint, **kwargs):
    instance.status_update()


@receiver(post_save, sender=ControlPoint)
def controlpoint_post_save_evidence(instance: ControlPoint, **kwargs):
    from .services.evidence import sync_control_point
    sync_control_point(instance)


@receiver(post_save, sender=IndicatorPoint)
def indicatorpoint_post_save_evidence(instance: IndicatorPoint, **kwargs):
    from .services.evidence import sync_indicator_point
    sync_indicator_point(instance)


@receiver(m2m_changed, sender=Control.conformity.through)
def control_conformity_evidence_sync(instance, action, **kwargs):
    if action in {'post_add', 'post_remove', 'post_clear'}:
        from .services.evidence import sync_control_point
        for point in instance.get_controlpoint():
            sync_control_point(point)


@receiver(m2m_changed, sender=Indicator.conformity.through)
def indicator_conformity_evidence_sync(instance, action, **kwargs):
    if action in {'post_add', 'post_remove', 'post_clear'}:
        from .services.evidence import sync_indicator_point
        for point in IndicatorPoint.objects.filter(indicator=instance):
            sync_indicator_point(point)


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
def human_evidence_saved(instance: HumanEvidence, **kwargs):
    from .services.evidence import evaluate_evidence
    evaluate_evidence(instance)


@receiver(post_save, sender=Evidence)
def evidence_saved(instance: Evidence, **kwargs):
    from .services.evidence import evaluate_evidence
    evaluate_evidence(instance)


@receiver(m2m_changed, sender=ControlPoint.attachment.through)
def controlpoint_attachment_evidence_sync(instance, action, **kwargs):
    if action in {'post_add', 'post_remove', 'post_clear'} and instance.pk:
        from .services.evidence import sync_control_point
        sync_control_point(instance)


@receiver(m2m_changed, sender=IndicatorPoint.attachment.through)
def indicatorpoint_attachment_evidence_sync(instance, action, **kwargs):
    if action in {'post_add', 'post_remove', 'post_clear'} and instance.pk:
        from .services.evidence import sync_indicator_point
        sync_indicator_point(instance)
