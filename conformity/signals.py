from django.db.models.signals import m2m_changed, pre_save, post_save
from django.dispatch import receiver
from .models import Organization, Requirement, Control, ControlPoint, Attachment, Action, Finding, Conformity, \
    Indicator, IndicatorPoint


@receiver(post_save, sender=Control)
def control_post_save_bootstrap(sender, instance: Control, **kwargs):
    Control.post_init_callback(instance)

@receiver(pre_save, sender=ControlPoint)
def controlpoint_pre_save_status(sender, instance: ControlPoint, **kwargs):
    ControlPoint.pre_save(sender, instance)

@receiver(pre_save, sender=Attachment)
def attachment_pre_save_mime(sender, instance: Attachment, **kwargs):
    Attachment.pre_save(sender, instance)

@receiver(pre_save, sender=Requirement)
def post_init_callback(instance, **kwargs):
    """This function keep hierarchy of the Requirement working on each Requirement instantiation"""
    if instance.parent:
        instance.name = f"{instance.parent.name}-{instance.code}"
    else:
        instance.name = instance.code

@receiver(m2m_changed, sender=Organization.applicable_frameworks.through)
def change_framework(instance, action, pk_set, *args, **kwargs):
    if action == "post_add":
        for pk in pk_set:
            instance.add_conformity(pk)

    if action == "post_remove":
        for pk in pk_set:
            instance.remove_conformity(pk)

@receiver(post_save, sender=Action)
def sync_findings_on_action_save(sender, instance: Action, **kwargs):
    """
    When an Action is saved (status/active may have changed),
    re-evaluate the archive state of all linked Findings.
    """
    for f in instance.associated_findings.all():
        f.update_archived()

@receiver(m2m_changed, sender=Action.associated_findings.through)
def sync_findings_on_m2m(sender, instance, action, reverse, pk_set, **kwargs):
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
def on_cp_saved(sender, instance: ControlPoint, **kwargs):
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
def on_action_saved(sender, instance: Action, **kwargs):
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
def indicator_post_save_bootstrap(sender, instance: Indicator, **kwargs):
    instance.indicator_point_init()

@receiver(pre_save, sender=IndicatorPoint)
def indicator_point_pre_save_ctrl(sender, instance: IndicatorPoint, **kwargs):
    instance.status_update()