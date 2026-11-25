# Complete reach endpoint diagnostics

This source successor repairs a specific gap between `SCORING_AND_CONTRASTS.md`
and the protected programme scorer. The predecessor admitted and retained raw
predictions but discarded the candidate raw descriptor before scoring. Its
report contained only projected scores, without target means, per-day error
denominators or counts of predictions changed by projection. Finite SSE and SST
could also produce a nonfinite ratio reported as a defined R².

The successor preserves the event-cued, retrospective question: released folded
vertical angle in degrees, magnitude in pixels and onset speed in pixels/second;
all 55 held-day folds within all 12 patients. It preserves the complete F/I ×
C/N/NC panel, selected T1 and D modules, reference selections, paired contrasts
and person bootstrap. The primary score remains projected prediction R²,
computed by pooling events within each person before averaging 12 person scores.
Raw scores are explicitly secondary diagnostics. Day-level R² is diagnostic and
never enters the macro average. A constant or empty day does not invalidate a
nonconstant, complete person; a constant or empty person still invalidates the
complete endpoint. Negative R² remains negative.

## Source changes

- `selection_worker.py` compares total inner SSE directly, as required by the
  scoring contract. Dividing equal-support SSE by the event count can round
  distinct totals to the same binary64 MSE and select a worse configuration or
  family under the tie rule. Exact SSE ties retain the declared ordering. The
  selector also requires all 25 configurations to have the same positive event
  count and finite, nonnegative SSE. No authentic reference selection was rerun.

- `admission.py` is a successor copy of the existing admission module with one
  change: it retains the already authenticated candidate raw descriptor. Every
  prior public-output, raw/projection, source, isolation and target-last check
  remains in place.
- `grade.py` reads raw and projected arrays through the same pinned reader. It
  emits complete raw and projected person summaries, per-day summaries and
  projection counts for each candidate, selected R1 reference family, strongest
  reference and training-mean baseline. Each summary retains `n`, target mean,
  SSE, SST and R²/status. The three target units are explicitly reported.
- `endpoint_metrics.py` checks the common projection relation, rejects invalid
  authentic label domains without clipping labels, and reports nonrepresentable
  SSE/SST/R² as `undefined_numerical_failure` with null unavailable numbers.
  Positive squared terms that underflow individually are accumulated exactly
  before final binary64 rounding. A positive full error/variation sum that
  still rounds to zero is a numerical failure, never exact-zero error or a
  constant person; representable aggregate subnormal sums remain available.
  The macro remains undefined when any required person is undefined. Ordinary
  `fsum / n` arithmetic is retained; a scaled compensated mean is used only when
  its intermediate sum overflows. Bootstrap deviations and interval endpoints
  must remain finite.

The report schema is `neural049_protected_score_v2`. Existing `scores`,
`contrasts`, `angle_intervals` and reference-anchor fields retain their roles;
`raw_scores`, `day_diagnostics`, `units`, `primary_prediction_form` and
`raw_scores_role` are added. These reports remain protected operator outputs:
person/day identities and target statistics are not participant observations.

## Use and integration

`endpoint_metrics.py` is independently importable with the standard library.
`grade.py`, `admission.py` and `selection_worker.py` are replacement source bodies for the matching
programme instance; they use its original sibling modules. In a new isolated
source assembly, place all four successor modules beside the original programme
modules, selecting these three bodies instead of their predecessors. Both reference
selection and target-last selection verification must import the successor selector. Bind the
resulting full source closure and report schema before admission. The portable
release, runtime manifests, current contract, registry and original source pins
have deliberately not been rewritten. An existing sealed instance must not be
patched in place or admitted under its old pins.

The successor charges extra raw-array reads through the existing numerical
limits, doubles the relevant persistent prediction-list allocation allowance,
reserves per-day diagnostic storage even for zero-row days, and charges each
paired diagnostic calculation. Actual full-study resources and serialized
report limits must be qualified with the new closure; this component does not
increase an existing approved budget.

Run `test_endpoint_report.py` within the selected source-test allocation. It uses
generated values and a standard-library array-reader stand-in to exercise the
actual evaluation loop on all 55 day positions, 12 unequal-sized people,
27 selected model conditions and three endpoints. File custody, native array
loading, full reference selection and bootstrap execution are outside that
generated loop control. Selection controls exercise the actual predecessor rounding defect for both
configuration and family selection, exact ties and incomplete/invalid support.
Separate controls cover folded-angle arithmetic,
projection, unequal participant weighting, numerical overflow and rejection
before target reads when admission is incomplete.

## Qualification limits

No authentic source arrays, target tables, previous solver targets, model
weights or predictions were read. No downloads, fitting, model/LLM calls or
dependency installations were made. This is an endpoint source repair, not
scientific qualification or empirical decoding performance. Native census,
clock/channel identity, full reference computation and competence, physical
isolation, independent numerical parity and complete study execution remain
open. The predecessor's R2 independent-bank parity gate remains; a separate
R2 result table is still not delivered by this scoped repair.

Direct interpretation and typed-viewer delivery remain unimplemented. Neither
programme source nor generated scorer controls establish either capability.
The original continuous wrist-velocity forecast remains the unmet historical
question and is not replaced or claimed by this repair.
