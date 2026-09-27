"""Evidence synchronization and evaluation services."""

from datetime import datetime, time, timedelta

from django.db import transaction
from django.utils import timezone


def _day_start(value):
    value = datetime.combine(value, time.min)
    return timezone.make_aware(value, timezone.get_current_timezone())


def _exclusive_day_after(value):
    return _day_start(value + timedelta(days=1))


def _evaluate(conformities, at=None):
    for conformity in conformities:
        invalidate_human_arbitration(conformity, at=at)
        conformity.evaluate_evidence(at=at)


def _update_evidence(evidence, values):
    """Update through Model.save so auto timestamps and evaluation signals run."""
    for field, value in values.items():
        setattr(evidence, field, value)
    evidence.save(update_fields=[*values, 'updated_at'])


@transaction.atomic
def sync_control_point(point):
    """Create/update the common Evidence projection of a ControlPoint."""
    from conformity.models import ControlPoint, Evidence

    result = {
        ControlPoint.Status.COMPLIANT: Evidence.Result.POSITIVE,
        ControlPoint.Status.NONCOMPLIANT: Evidence.Result.NEGATIVE,
    }.get(point.status, Evidence.Result.NEUTRAL)
    values = {
        'source_type': Evidence.SourceType.CONTROL,
        'result': result,
        'valid_from': _day_start(point.period_start_date),
        'valid_to': _exclusive_day_after(point.period_end_date),
        'evaluated_at': point.control_date,
        'evaluator': point.control_user,
        'comment': point.comment,
    }
    if point.evidence_id:
        evidence = Evidence.objects.get(pk=point.evidence_id)
        _update_evidence(evidence, values)
    else:
        evidence = Evidence.objects.create(**values)
        type(point).objects.filter(pk=point.pk).update(evidence=evidence)
        point.evidence = evidence
    evidence.conformities.set(point.control.conformity.all() if point.control_id else [])
    evidence.attachments.set(point.attachment.all())
    _evaluate(evidence.conformities.all())
    return evidence


@transaction.atomic
def sync_indicator_point(point):
    """Create/update the common Evidence projection of an IndicatorPoint."""
    from conformity.models import Evidence, IndicatorPoint

    result = {
        IndicatorPoint.Status.COMPLIANT: Evidence.Result.POSITIVE,
        IndicatorPoint.Status.CRITICAL: Evidence.Result.NEGATIVE,
    }.get(point.status, Evidence.Result.NEUTRAL)
    values = {
        'source_type': Evidence.SourceType.INDICATOR,
        'result': result,
        'valid_from': _day_start(point.period_start_date),
        'valid_to': _exclusive_day_after(point.period_end_date),
        'evaluated_at': point.control_date,
        'evaluator': point.control_user,
        'comment': point.comment,
    }
    if point.evidence_id:
        evidence = Evidence.objects.get(pk=point.evidence_id)
        _update_evidence(evidence, values)
    else:
        evidence = Evidence.objects.create(**values)
        type(point).objects.filter(pk=point.pk).update(evidence=evidence)
        point.evidence = evidence
    evidence.conformities.set(point.indicator.conformity.all() if point.indicator_id else [])
    evidence.attachments.set(point.attachment.all())
    _evaluate(evidence.conformities.all())
    return evidence


def invalidate_human_arbitration(conformity, at=None):
    """Close human arbitration when operational evidence no longer supports it."""
    from conformity.models import Evidence

    at = at or timezone.now()
    operational = conformity.evidence.valid_at(at).operational()
    results = set(operational.values_list('result', flat=True))
    positive = Evidence.Result.POSITIVE in results
    negative = Evidence.Result.NEGATIVE in results
    humans = conformity.evidence.valid_at(at).filter(source_type=Evidence.SourceType.HUMAN)
    for human in humans:
        changed_after_arbitration = operational.filter(
            result_updated_at__gt=human.created_at
        )
        contradicted = (
            (
                human.result == Evidence.Result.POSITIVE
                and changed_after_arbitration.filter(result=Evidence.Result.NEGATIVE).exists()
            )
            or (
                human.result == Evidence.Result.NEGATIVE
                and changed_after_arbitration.filter(result=Evidence.Result.POSITIVE).exists()
            )
            or (human.result == Evidence.Result.PARTIAL and positive != negative)
        )
        if contradicted:
            human.valid_to = max(at, human.valid_from + timedelta(microseconds=1))
            human.save(update_fields=['valid_to', 'updated_at'])


def evaluate_evidence(evidence, at=None):
    """Re-evaluate all assessments affected by an Evidence change."""
    _evaluate(evidence.conformities.all(), at=at)
