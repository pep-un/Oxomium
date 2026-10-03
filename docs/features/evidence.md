# Evidence-based conformity evaluation

Oxomium represents a fact used in an assessment with the common `Evidence`
model. One evidence record may support several `Conformity` records; this
reuses operational work without asserting that framework requirements are
equivalent. Evidence records never reference other evidence records.

## Validity

Validity is a half-open interval:

```text
valid_from <= timestamp < valid_to
```

`valid_to = NULL` means that no end of validity is known. The `valid_at()` and
`current()` queryset methods are the canonical way to select valid records.
Ending validity preserves history; evidence is not deleted to invalidate it.

## Results and conformity states

Evidence result and source lifecycle are separate concepts. A scheduled or
missed collection is lifecycle information and therefore contributes a neutral
result rather than a positive or negative conclusion.

| Current operational evidence | Conformity evidence state |
| --- | --- |
| none, or neutral only | Not evaluated |
| positive only | Compliant |
| negative only | Non-compliant |
| positive and negative | Inconclusive |

A valid `HumanEvidence` may arbitrate a mixed set as compliant, partially
compliant, or non-compliant. New contradictory operational evidence closes its
validity interval automatically. A partial decision remains valid only while
the operational set remains mixed.

Categorical `evidence_state` is stored separately from the existing numeric
framework metric. For leaf requirements an unambiguous or human-arbitrated
state updates the compatibility metric to 100, 50, or 0 with `EVID` provenance.
Existing parent aggregation remains an explicit operation, so the migration
does not silently recalculate historical framework totals.

## Sources

- `ControlPoint`: compliant is positive, non-compliant is negative; lifecycle
  states are neutral.
- `IndicatorPoint`: compliant is positive, critical is negative, and warning or
  lifecycle states are neutral.
- `HumanEvidence`: expert assessment used to arbitrate evidence.
- `Finding`: audit findings are first-class Evidence. Severity remains
  Finding-specific; positive findings map to positive Evidence,
  critical/major/minor findings map to negative Evidence, and observation/other
  findings map to neutral Evidence.
- `DocumentEvidence`: a Document with an explicit result and assessment association.
- Base `Evidence`: a generic explicitly entered fact; no separate manual subtype is needed.

ControlPoint, IndicatorPoint, Finding, HumanEvidence and DocumentEvidence are concrete subclasses of Evidence.
Common validity, result, evaluator, comment, attachments and Conformity
relationships are stored once on Evidence; only source-specific fields remain
on the subclasses. Finding validity replaces the former archived flag:
`valid_to` may be set manually and is closed automatically when all linked
corrective Actions are completed. Legacy period/evaluator accessors
are compatibility aliases, not duplicated persistence.

Periodic Control and Periodic Indicator are configured directly against organization-specific
Conformity records. They do not reference Requirement or Organization directly.
Each periodic Evidence snapshots those Conformity targets; completed Evidence
keeps its historical associations. The data
migration converts existing points into Evidence subclasses, preserves action
links and target relationships, migrates expert assessments to HumanEvidence
when their meaning is unambiguous, and preserves finding/document evidence without inventing framework
relationships.

## Human arbitration

Authenticated users can record a human assessment from a leaf Conformity edit
page. The author and evaluation time are captured automatically. Human evidence
is displayed with the complete evidence history on the same page.

See [Evidence and HumanEvidence arbitration](evidence-arbitration.md) for the
complete decision table, invalidation rules, target synchronization contract,
and simplification opportunities.
