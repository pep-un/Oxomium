# Evidence and HumanEvidence arbitration

This page documents how Oxomium derives a leaf `Conformity.evidence_state`
from current Evidence and how a `HumanEvidence` decision participates in that
calculation.

## Responsibilities

The model deliberately separates three concepts:

1. **Target configuration** — `Control.requirements` and
   `Indicator.requirements` say which requirements an operational source is
   intended to assess.
2. **Assessment association** — `Evidence.conformities` records which concrete
   organization-specific Conformity records a particular fact actually
   contributes to.
3. **Computed state** — `Conformity.evidence_state` is derived from the
   currently valid Evidence attached to that Conformity.

Target configuration is therefore not assessment history. Once an Evidence
exists, its `conformities` relation is the authoritative record of where that
fact applies.

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

## Target synchronization

ControlPoint and IndicatorPoint are Evidence themselves. When they are created,
their concrete `Evidence.conformities` associations are initialized from their
source's configured Requirement targets.

When `Control.requirements` or `Indicator.requirements` changes, signals
currently resynchronize the existing points' `conformities` sets.

This makes `Evidence.conformities` a materialized relation derived from target
configuration for periodic operational Evidence, while manually associated
Evidence types use `Evidence.conformities` directly.

### Invariant

Code that asks **what a Control or Indicator is configured to cover** should
read `requirements`.

Code that asks **which facts currently support a concrete assessment** or
computes conformity must read `Evidence.conformities` / `Conformity.evidence`.

Do not compute a Conformity state directly from `Control.requirements` or
`Indicator.requirements`.

## Simplification opportunities

The current design is workable, but the synchronization contract can be made
clearer.

### 1. Centralize target resolution

Both ControlPoint and IndicatorPoint signals independently translate
`requirements` into organization-specific Conformity records. A single helper
such as `resolve_target_conformities(source)` and a single synchronization
service would remove duplicated rules and make the invariant testable in one
place.

### 2. Name configuration and evidence relations explicitly

Compatibility APIs named `conformity` can blur the distinction between a
Requirement target and an Evidence association. New code should prefer
`requirements`, `target_requirements`, or similarly explicit terminology
for configuration and reserve `conformities` for concrete Evidence
associations.

Legacy adapters can then be deprecated without changing the persisted model.

### 3. Keep arbitration out of signals

Signals should remain thin event adapters. They should not acquire additional
business rules. Keeping all state derivation and HumanEvidence invalidation in
`services/evidence.py` prevents multiple implementations of arbitration.

### 4. Make synchronization policy explicit

Changing a Control/Indicator target currently rewrites the `conformities`
relation of existing points. That is simple, but it also changes which
historical Evidence is associated with assessments.

If historical association is intended to be immutable, future target changes
should affect only new Evidence. If retroactive retargeting is intended, the
current behavior should be retained and covered by an explicit regression test.
This policy should be decided before removing the compatibility layer.

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
