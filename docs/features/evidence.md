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
- `HumanEvidence`: explicit human arbitration.
- `FindingEvidence`: positive findings are positive, critical/major/minor
  findings are negative, and other findings are neutral.
- `DocumentEvidence`: a documentary attachment with an explicit result and
  assessment association.
- `ManualEvidence`: a simple explicitly entered fact.

ControlPoint and IndicatorPoint are concrete subclasses of Evidence. Common
validity, result, evaluator, comment, attachments and Conformity relationships
are stored once on Evidence; only Control/Indicator-specific lifecycle and
measurement fields remain on the subclasses. Legacy period/evaluator accessors
are compatibility aliases, not duplicated persistence.

Control and Indicator keep only Requirement target configuration. Concrete
assessment relationships live exclusively on Evidence.conformities. The data
migration converts existing points into Evidence subclasses, preserves action
links and target relationships, migrates expert assessments to HumanEvidence
when their meaning is unambiguous, and creates unassociated finding/document
records without inventing framework relationships.

## Human arbitration

Authenticated users can record a human assessment from a leaf Conformity edit
page. The author and evaluation time are captured automatically. Human evidence
is displayed with the complete evidence history on the same page.

See [Evidence and HumanEvidence arbitration](evidence-arbitration.md) for the
complete decision table, invalidation rules, target synchronization contract,
and simplification opportunities.
