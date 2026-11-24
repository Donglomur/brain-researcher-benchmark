# Complete paired Figure 3C comparison

This trusted operator component compares two complete committed prediction stores
on the selected original Figure 3C endpoint. It fills the missing complete-panel
pairing step. It does not admit reproduction or improvement, fit a model, execute
a participant, or qualify a reference as the original author baseline.

The original [prediction interface](../prediction-interface-v1/README.md) already
validates and scores all 2,054 coordinates. This component authenticates and reuses
that exact interface. Both methods must share the identical source plan, input
bindings, 12-fold assignments, column branch, 79-electrode roster and declared
assistance condition before either evaluator is called. Compare each assistance
condition separately; this is not a comparison between assistance conditions.

Both DN-none and DN-S source coordinate slots are retained. They are labels, not
proof of either method's architecture. DN-S remains the required stronger author
comparison, and improved DN-none values alone do not establish a paper win.

```python
from compare import Source, compare

source = Source()  # pinned sibling prediction interface
# reference_protocol and candidate_protocol are separately frozen original
# Protocol objects with different method identities but identical support.
report = compare(
    reference_store, reference_protocol, frozen_reference_manifest_sha256,
    candidate_store, candidate_protocol, frozen_candidate_manifest_sha256,
    protected_input_root, bootstrap_seed=17, source=source,
)
```

The reference role is an operator selection, not an author-authentication claim.
A calibrated author baseline must separately provide the complete prediction
store through the existing interface and documented source execution evidence.
No saved author parameter score is relabeled as an authenticated prediction.

Each unchanged evaluator authenticates its complete committed store before it
reads protected targets. Both read the same operator-owned input root, whose
contents are checked against their common frozen source bindings. Filesystem
custody and participant isolation remain external requirements. The method that
runs first is not given information about the second; this component runs no
participant programme. Both methods must already be frozen.

The report retains both original score reports and their complete condition,
fold, electrode and regional arrays. Additional candidate-minus-reference
differences preserve all 1,896 held-fold cells, 158 electrode/model-slot scores
and six region/model-slot medians. Raw and source-rounded condition differences
are separate. Failures and undefined scores remain present; undefined values
become `null` differences, never zero. A full-data failure keeps the source
scorer's global regional gate. All 158 full-data coordinate identities and
failure records remain in the original reports; prediction arrays remain in the
committed stores.

No whole-cohort scalar, win count, threshold or paired confidence interval is
introduced. The existing 1,000-resample 68% electrode bootstrap is descriptive
within each method. Both scorers use the same declared seed, but skipped undefined
groups can advance their RNG streams differently; these intervals are never
reported as uncertainty for differences. Participant dependence, original
publication input/branch/runtime parity, original author-result calibration,
reproduction tolerance and a complete-region superiority rule remain unresolved.
All scientific decisions remain `unresolved`, even when every difference is
positive. Generated controls cannot establish scientific improvement.

## Source and controls

The [pinned author Figure 3 script](https://raw.githubusercontent.com/ABra1993/tAdaptation_ECoG/09cd778fac545d406cba39ba408f0f00fbe39975/mkFigure3.py)
retains three regions and none/S scaling, taking a median of 1,000 bootstrap
medians with 16th/84th percentiles. This component preserves that separate array
through the unchanged scorer instead of inventing an original scalar reduction.
[DEPENDENCIES.json](DEPENDENCIES.json) records exact current dependencies.

Run `python3 test_compare.py` in this directory with Python 3.11+ and existing
NumPy. `TEMPORAL_INTERFACE_DIR` may locate the exact pinned sibling interface in
another trusted checkout. Set `TEMPORAL_GENERATED_ROOT` to an owned scratch path
and `PYTHONDONTWRITEBYTECODE=1` to avoid bytecode artifacts. No install, download,
authentic dataset or model is needed. Allow 6 MiB cumulative generated writes and
120 seconds per process; the measured run is much smaller and faster.

Six analytical controls execute the actual complete Protocol and source reducer,
with a declared evaluator seam for pair orchestration. They cover both source
branches and both assistance conditions, changed folds/branches/conditions,
complete granular deltas, missing support, failures and undefined values. One
additional control writes and seals a complete 2,054-record all-failure store,
then compares it to itself through the real evaluator without reading targets.
That same-method control verifies transport and failure retention, not a distinct
method comparison or successful prediction. Existing scorer numeric and durable
transport tests retain their earlier scopes and are not claimed as rerun here.
