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


def _automatic_state(conformity, at):
    """Evaluate valid non-human Evidence according to the business truth table."""
    from conformity.models import Evidence

    results = set(
        _current_evidence(conformity, at)
        .exclude(source_type=Evidence.SourceType.HUMAN)
        .values_list('result', flat=True)
    )
    if not results:
        return conformity.EvidenceState.NOT_EVALUATED
    if Evidence.Result.PARTIAL in results:
        return conformity.EvidenceState.PARTIAL

    positive = Evidence.Result.POSITIVE in results
    negative = Evidence.Result.NEGATIVE in results
    if positive and negative:
        return conformity.EvidenceState.INCONCLUSIVE
    if positive:
        return conformity.EvidenceState.COMPLIANT
    if negative:
        return conformity.EvidenceState.NON_COMPLIANT
    return conformity.EvidenceState.INCONCLUSIVE


def _human_state(conformity, human):
    """Map one valid HumanEvidence conclusion to a Conformity evidence state."""
    from conformity.models import Evidence

    if human is None:
        return None
    return {
        Evidence.Result.POSITIVE: conformity.EvidenceState.COMPLIANT,
        Evidence.Result.NEGATIVE: conformity.EvidenceState.NON_COMPLIANT,
        Evidence.Result.PARTIAL: conformity.EvidenceState.PARTIAL,
        Evidence.Result.NEUTRAL: conformity.EvidenceState.INCONCLUSIVE,
    }.get(human.result)


def _combine_states(conformity, automatic, human):
    """Combine current automatic state with the active human arbitration."""
    if human is None:
        return automatic

    human_state = _human_state(conformity, human)
    if automatic in {
        conformity.EvidenceState.NOT_EVALUATED,
        conformity.EvidenceState.INCONCLUSIVE,
    }:
        return human_state

    if automatic == conformity.EvidenceState.PARTIAL:
        return human_state

    if human_state == conformity.EvidenceState.PARTIAL:
        return conformity.EvidenceState.PARTIAL

    if automatic == human_state:
        return automatic

    # A direct human/automatic disagreement expresses partial conformity.
    if {
        automatic,
        human_state,
    } == {
        conformity.EvidenceState.COMPLIANT,
        conformity.EvidenceState.NON_COMPLIANT,
    }:
        return conformity.EvidenceState.PARTIAL

    return human_state


def _active_human(conformity, at):
    from conformity.models import Evidence

    return (
        _current_evidence(conformity, at)
        .filter(source_type=Evidence.SourceType.HUMAN)
        .order_by('-valid_from', '-pk')
        .first()
    )


def _state_from_current_evidence(conformity, at):
    automatic = _automatic_state(conformity, at)
    return _combine_states(conformity, automatic, _active_human(conformity, at))


def _close_human_evidence(human, at):
    """Close one arbitration without deleting its historical conclusion."""
    if human.valid_to is not None and human.valid_to <= at:
        return False

    human.valid_to = max(at, human.valid_from + timedelta(microseconds=1))
    human.save(update_fields=['valid_to', 'updated_at'])
    return True


def _human_is_compatible(conformity, automatic, human):
    """Return whether an arbitration remains valid for the current auto state."""
    from conformity.models import Evidence

    if automatic in {
        conformity.EvidenceState.NOT_EVALUATED,
        conformity.EvidenceState.INCONCLUSIVE,
    }:
        return True
    compatible = {
        conformity.EvidenceState.COMPLIANT: {
            Evidence.Result.POSITIVE,
            Evidence.Result.PARTIAL,
        },
        conformity.EvidenceState.NON_COMPLIANT: {
            Evidence.Result.NEGATIVE,
            Evidence.Result.PARTIAL,
        },
        conformity.EvidenceState.PARTIAL: {
            Evidence.Result.PARTIAL,
        },
    }
    return human.result in compatible.get(automatic, set())


def invalidate_human_arbitration(conformity, *, trigger=None, at=None):
    """Close human arbitration made obsolete by a changed automatic situation.

    A human Evidence addition replaces the previous arbitration. Automatic
    Evidence changes use the agreed compatibility table; merely changing the
    set of Evidence does not invalidate an otherwise compatible arbitration.
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

    changed = False
    if trigger is not None and trigger.source_type == Evidence.SourceType.HUMAN:
        for human in humans:
            if human.pk != trigger.pk:
                changed = _close_human_evidence(human, at) or changed
        return changed

    # Compatibility is re-evaluated only after a semantic automatic Evidence
    # change. A normal read must not retroactively reinterpret an arbitration.
    if trigger is None or trigger.source_type == Evidence.SourceType.HUMAN:
        return changed

    automatic = _automatic_state(conformity, at)
    for human in humans:
        if not _human_is_compatible(conformity, automatic, human):
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
