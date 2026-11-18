# Importing retained context predictions

`legacy_import.py` connects the retained NEURAL-068 per-context answer format to
this component's current paired-session scorer. It is a trusted operator
transformation. It does not launch a participant, train a decoder, open targets,
load NWB/NPZ files, or import the historical scoring implementation.

The retained protocol emits 84 separate answers using
`neural068-prefix-5-10-third-segment-v1`. Each contains `schema`, `packet_id`,
`context_id`, and `predictions`. Those predictions are ordered over the recorded
third-segment query interval. The current scorer requires an explicit ordered row
ID for every prediction, a current layout packet ID, and all 84 contexts together.

The import requires a trusted, frozen current layout, the complete legacy pool
metadata, all 84 captured answers, and an expected legacy packet ID selected
outside participant control. It checks:

- The legacy canonical pool digest, including its ASCII encoding and trailing
  newline, against that externally selected ID.
- The 13 training and 14 query runs in their original order and partition.
- The seven labels in their original coordinate order.
- Each query's original NWB hash, complete third-segment interval, scored-row
  count, and 0/5/10-second calibration counts against the current layout.
- Every answer's generation and context identity, complete row count, and seven
  finite nonboolean values per row.

Only then does it add the exact native-bin row IDs and build a submission for
`scorer.validate_submission`. Prediction values are copied without fitting,
masking, reordering, averaging, interpolation, rounding, or selecting budgets.

```python
submission = legacy_import.convert(
    trusted_layout,
    trusted_legacy_pool_metadata,
    all_84_captured_answers,
    expected_legacy_packet_id=frozen_legacy_packet_id,
)
# After independent lifecycle/packet qualification, the operator may pass this
# submission to scorer.score with its protected target loader.
```

The transformation does not convert a historical *score* into a new score. The
old grader used mean run-level energy R² and absolute neural-clock performance at
10 seconds as its primary result. The current grader pools sets within the seven
source sessions, then reports equally weighted paired R² gains at each budget.
Old aggregate reports cannot recover the required predictions.

## Qualification boundaries

A self-consistent hash is not source authenticity. The trusted operator must
independently authenticate the source files, freeze the layout and legacy packet
selection, and bind each captured answer to its admitted participant lifecycle.
The layout's full evaluation mask must come from authenticated preparation. The
legacy pool metadata records only the scored-row count; matching that count does
**not** independently prove equality of its mask bitmap. This importer neither
opens the original mask nor claims such a comparison.

The importer also cannot establish unchanged-decoder competence, pre-query method
freezing, exact calibration-only adaptation, causal signal availability, fresh
case state, cross-task 067/068 exposure, or permission to redistribute data. Those
existing holds remain. All observations concern one participant. Session repeats
do not establish human-population generalization. A numerical import is neither
direct neural interpretation nor a typed-viewer evaluation.

The seven generated controls cover complete conversion into the current scorer,
independent output copies, immutable generation selection, source/split/prefix
and channel mismatch, missing/extra contexts, incorrect answer identity, malformed
predictions, and the retained canonical digest convention. They use no authentic
arrays, labels, candidate outputs, decoder fits, or empirical performance data.
This component is not execution admission or a readiness promotion.

The source identities used to define the bridge are in
`legacy_import_sources.json`. Their paths are provenance references, not runtime
dependencies of the importer. Before publication, enroll `test_legacy_import.py`
beside the current paired-session component tests; it is not covered by a command
that explicitly runs only `test_scorer.py`.
