# Evidence and HumanEvidence arbitration

This page documents how Oxomium derives a leaf `Conformity.evidence_state`
from current Evidence and how a `HumanEvidence` decision participates in that
calculation.

## Responsibilities

The domain model separates normative definitions, organization context, control
configuration, and observations:

1. **Requirement** is an abstract requirement from a Framework. It has no
   organization-specific assessment context.
2. **Conformity** contextualizes one Requirement for one Organization. It is the
   only object that joins those two concepts.
3. **Control** and **Indicator** target concrete Conformity records. They do not
   reference Requirement or Organization directly; their context comes
   exclusively from Conformity.
4. **Evidence** records a fact and the concrete Conformity records to which that
   fact contributes.

A ControlPoint or IndicatorPoint is itself Evidence. When a periodic point is
created, its `Evidence.conformities` relation is initialized as a snapshot of
the source Control/Indicator `conformity` relation. Later changes to the
Control/Indicator configuration do not rewrite historical Evidence.

This gives two distinct relations with different meanings:

- `Control/Indicator.conformity`: what the source is configured to assess.
- `Evidence.conformities`: what a particular historical fact contributes to.

Neither relation is derived through Requirement.

## Validity window

Only Evidence valid at the evaluation timestamp participates in arbitration:

```text
valid_from <= timestamp < valid_to
```

A null `valid_to` means that the Evidence has no known end. Invalidating a
HumanEvidence closes its validity window instead of deleting it, preserving the
audit trail.

## Operational Evidence

All current non-human Evidence is reduced to the presence of positive and
negative conclusions. Neutral Evidence does not decide conformity.

| Current operational conclusions | State before human arbitration |
| --- | --- |
| none / neutral only | Not evaluated |
| positive only | Compliant |
| negative only | Non-compliant |
| positive + negative | Inconclusive |

The engine always evaluates the complete current Evidence set; it does not
incrementally mutate the state from the previous result.

## HumanEvidence

A current HumanEvidence maps its result to a state:

| HumanEvidence result | State |
| --- | --- |
| positive | Compliant |
| partial | Partially compliant |
| negative | Non-compliant |

When operational Evidence is mixed, the most recent current HumanEvidence
(`valid_from`, then primary key) arbitrates the otherwise inconclusive state.

When there is no positive or negative operational conclusion, a current
HumanEvidence may also provide the state. This preserves standalone and
migrated expert assessments.

When operational Evidence is unambiguous (positive-only or negative-only), the
operational conclusion wins. HumanEvidence does not override an unambiguous
operational set.

## Automatic invalidation

Before calculating a state, the engine checks whether active HumanEvidence has
become obsolete.

A positive human decision is closed when a newly triggering, currently valid
non-human Evidence is negative. A negative human decision is closed when the
trigger is positive.

A partial human decision has different semantics: once operational conclusions
exist, it remains valid only while both positive and negative operational
Evidence are current. If the operational set becomes unambiguous, the partial
decision is closed.

The trigger can be a newly created/updated Evidence or an existing Evidence
newly associated with a Conformity. This is intentional: association time can
introduce a new contradiction even when the Evidence itself is old.

Closing uses the evaluation timestamp as `valid_to` (with a minimal
microsecond interval when necessary), so the historical decision remains
auditable.

## Evaluation flow

For one Conformity the service performs these steps:

```text
Evidence or association changes
        |
        v
invalidate_human_arbitration()
        |
        v
select all Evidence valid now
        |
        +--> non-human: detect positive / negative conclusions
        |
        +--> human: select latest current HumanEvidence
        |
        v
derive evidence_state
        |
        v
persist leaf compatibility metric
        |
        v
recompute parent aggregation when the leaf changed
```

The implementation lives in `conformity/services/evidence.py`. Signals in
`conformity/signals.py` should only notify this service of model or association
changes; arbitration rules belong in the service.

## Periodic source targeting

A Control or Indicator is configured directly against one or more Conformity
records. It has no direct Requirement or Organization relation.

When a ControlPoint or IndicatorPoint is created, the current source
Conformities are copied to the Evidence. This is a creation-time snapshot, not
a permanently synchronized relation.

### Invariant

Code that asks **what a Control or Indicator is configured to assess** reads
`source.conformity`.

Code that asks **which assessments a historical fact supports** reads
`Evidence.conformities`.

Code must never reconstruct a Conformity from a Requirement plus an
Organization for periodic sources.

## Simplification opportunities

The architecture should remain deliberately small:

- keep Requirement purely normative;
- keep organization context only on Conformity;
- keep Control/Indicator targeting only on Conformity;
- snapshot those targets onto each periodic Evidence at creation;
- keep arbitration rules in `services/evidence.py`, with signals acting only
  as event adapters.

No compatibility adapter should translate Conformity to Requirement and back.
Such an adapter hides a loss of domain context and creates competing paths to
the same assessment.

## Regression cases

Changes to arbitration should cover at least:

- positive-only, negative-only, mixed and neutral-only operational sets;
- standalone positive, partial and negative HumanEvidence;
- human arbitration of a mixed operational set;
- a later contradictory Evidence closing positive/negative HumanEvidence;
- an old Evidence newly associated to a Conformity acting as a contradiction;
- partial HumanEvidence closing when a mixed set becomes unambiguous;
- removal and re-addition of contradictory Evidence;
- expiry through `valid_to` followed by time-bound state refresh;
- multiple current HumanEvidence records, where the latest one is selected.
