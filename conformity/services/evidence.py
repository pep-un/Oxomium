"""Evidence evaluation services.

ControlPoint and IndicatorPoint inherit Evidence directly. No projection or
field synchronization layer is required.
"""

from datetime import timedelta

from django.utils import timezone


def _evaluate(conformities, at=None):
    for conformity in conformities:
        invalidate_human_arbitration(conformity, at=at)
        conformity.evaluate_evidence(at=at)


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
