"""Evidence evaluation engine.

All Evidence sources, including ControlPoint and IndicatorPoint, go through
this module. Signals only notify this service that an Evidence or association
changed; the evaluation rules live here.
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone


def _current_evidence(conformity, at):
    return conformity.evidence.valid_at(at)


def _operational_flags(conformity, at):
    from conformity.models import Evidence

    results = set(
        _current_evidence(conformity, at)
        .exclude(source_type=Evidence.SourceType.HUMAN)
        .values_list('result', flat=True)
    )
    return (
        Evidence.Result.POSITIVE in results,
        Evidence.Result.NEGATIVE in results,
    )


def _state_from_current_evidence(conformity, at):
    """Return the categorical state derived from currently valid Evidence."""
    from conformity.models import Evidence

    current = _current_evidence(conformity, at)
    operational = current.exclude(source_type=Evidence.SourceType.HUMAN)
    results = set(operational.values_list('result', flat=True))
    positive = Evidence.Result.POSITIVE in results
    negative = Evidence.Result.NEGATIVE in results

    if positive and negative:
        human = (
            current
            .filter(source_type=Evidence.SourceType.HUMAN)
            .order_by('-valid_from', '-pk')
            .first()
        )
        if human is None:
            return conformity.EvidenceState.INCONCLUSIVE
        return {
            Evidence.Result.POSITIVE: conformity.EvidenceState.COMPLIANT,
            Evidence.Result.NEGATIVE: conformity.EvidenceState.NON_COMPLIANT,
            Evidence.Result.PARTIAL: conformity.EvidenceState.PARTIAL,
        }.get(human.result, conformity.EvidenceState.INCONCLUSIVE)

    if positive:
        return conformity.EvidenceState.COMPLIANT
    if negative:
        return conformity.EvidenceState.NON_COMPLIANT
    return conformity.EvidenceState.NOT_EVALUATED


def _close_human_evidence(human, at):
    """Close one arbitration without deleting its historical conclusion."""
    if human.valid_to is not None and human.valid_to <= at:
        return False

    human.valid_to = max(at, human.valid_from + timedelta(microseconds=1))
    human.save(update_fields=['valid_to', 'updated_at'])
    return True


def invalidate_human_arbitration(conformity, *, trigger=None, at=None):
    """Invalidate active human arbitration when the triggering fact contradicts it.

    The trigger is important: an Evidence may have been created long ago and
    only now attached to this Conformity. Association time must therefore count
    as a new contradiction; comparing Evidence.created_at/result_updated_at is
    insufficient.
    """
    from conformity.models import Evidence

    at = at or timezone.now()
    humans = list(
        _current_evidence(conformity, at)
        .filter(source_type=Evidence.SourceType.HUMAN)
        .order_by('-valid_from', '-pk')
    )
    if not humans:
        return False

    positive, negative = _operational_flags(conformity, at)
    changed = False

    for human in humans:
        contradicted = False

        if human.result == Evidence.Result.PARTIAL:
            # Partial arbitration is meaningful only while evidence is mixed.
            contradicted = not (positive and negative)
        elif (
            trigger is not None
            and trigger.source_type != Evidence.SourceType.HUMAN
            and trigger.is_valid_at(at)
        ):
            contradicted = (
                human.result == Evidence.Result.POSITIVE
                and trigger.result == Evidence.Result.NEGATIVE
            ) or (
                human.result == Evidence.Result.NEGATIVE
                and trigger.result == Evidence.Result.POSITIVE
            )

        if contradicted:
            changed = _close_human_evidence(human, at) or changed

    return changed


def _persist_state(conformity, state, at):
    """Persist leaf compatibility status and propagate parent aggregation."""
    previous_status = conformity.status
    previous_state = conformity.evidence_state

    conformity._persist_evidence_state(state, at)

    if conformity.requirement.is_leaf_node() and (
        conformity.status != previous_status or state != previous_state
    ):
        from conformity.services.conformities import recompute_parent_chain

        parent = conformity.get_parent()
        if parent is not None:
            recompute_parent_chain(parent)


@transaction.atomic
def evaluate_conformity(conformity, *, at=None, trigger=None, persist=True):
    """Recompute one Conformity from the complete current Evidence set."""
    at = at or timezone.now()

    # Close obsolete/contradicted arbitration first so it cannot influence the
    # state selected below.
    invalidate_human_arbitration(conformity, trigger=trigger, at=at)

    state = _state_from_current_evidence(conformity, at)
    if persist:
        _persist_state(conformity, state, at)
    return state


def evaluate_evidence(evidence, *, at=None, contradiction=True):
    """Recompute every Conformity associated with a changed Evidence."""
    at = at or timezone.now()
    trigger = evidence if contradiction else None
    for conformity in evidence.conformities.select_related('requirement').all():
        evaluate_conformity(conformity, at=at, trigger=trigger)


def evaluate_conformities(conformities, *, at=None):
    """Recompute Conformities when no single Evidence is the trigger."""
    at = at or timezone.now()
    for conformity in conformities:
        evaluate_conformity(conformity, at=at)

def refresh_time_bound_conformities(*, at=None):
    """Refresh persisted states whose truth may have changed only with time."""
    from conformity.models import Conformity

    at = at or timezone.now()
    conformities = (
        Conformity.objects
        .filter(evidence__isnull=False)
        .select_related('requirement')
        .distinct()
    )
    evaluate_conformities(conformities, at=at)
