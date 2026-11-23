# Complete Siena leave-one-person-out evaluation

The existing Siena scorer evaluates complete recordings for selected patients.
This operator component enforces a prospective complete outer study: exactly
14 folds, one held-out person per fold, all 41 source recordings evaluated once,
and each frozen artifact declaring the other 13 people as its training set.
This is one explicit study protocol; the generic selected-patient evaluator
remains available for other declared splits.

The component uses the unchanged, pinned `occupancy-evaluator-v2` and its pinned
`initial-evaluator-v1` dependency. It adds orchestration and support checks,
without changing event matching, tolerance, record boundaries, thresholds or
patient metrics. No authentic EEG or model performance was evaluated to create
this source.

## Accepted inputs and recipe consistency

The Python API `evaluate_folds(folds)` takes a list of 14 dictionaries. Each has
`manifest`, `predictions` and `frozen`, with the same values accepted by the
existing occupancy evaluator. Optional `comparator_predictions` and
`comparator_frozen` must appear together in every fold. The same private
evaluation manifest is used for both arms within a fold. Missing patients,
repeated held-out people, incomplete recordings, leakage and partial comparator
coverage are rejected.

Only the existing `line_length_v1` and `timing_only_v1` reference artifacts are
accepted. Within each arm, all folds must declare the same method, ordered
channels, fixed feature parameters, scoring policy and threshold-selection
rule. Train-fitted scales/rates, threshold, training summary and training
manifest hash may vary by fold. Paired arms must use identical training-manifest
hashes and patient order within each fold, as required by the preserved scorer.
These checks validate declarations; they do not prove actual training provenance.

## Aggregation and interpretation

Per-patient metrics are copied from the preserved scorer. Event F1 and
sensitivity keep their existing defined-only patient means and explicit
undefined-person lists. False alarms retain the scorer's rounded 10 Hz time
denominator. Alarm occupancy retains exact complete sample-grid duration,
duration weighting within people and equal-person weighting across people.
Always-negative and always-positive controls cover the same complete support.

`complete_declared_outer_coverage` reports roster and recording coverage.
`full_cohort_event_f1_defined` is false if any person's F1 is undefined; the
paired analogue requires defined endpoints for all 14 people in both arms.
Neither flag establishes authenticated source data or scientific qualification.
Optional paired F1 bootstrap and occupancy differences reuse the existing
descriptive patient comparison. Shared training data across outer folds and
clinical selection limit inferential interpretation. No acceptance cutoff,
paper-win rule or clinical utility claim is added.

## Command line

Create an operator-private JSON study document:

```json
{
  "schema_version": 1,
  "task_id": "NEURAL-011",
  "folds": [
    {
      "manifest": "PN00-test-private.json",
      "predictions": "PN00-scores.npz",
      "frozen": "PN00-reference.json"
    }
  ]
}
```

The abbreviated example shows one entry; execution requires all 14 folds.
Paths are relative to the study document. The CLI invokes the same API:

```sh
python siena_lopo.py study-private.json report-private.json
python -B tests/test_lopo.py -v
```

The report includes reference events and must stay operator-private. All fold
prediction arrays are loaded in memory; provision memory for the complete study.
The generated controls use small arrays and do not qualify full-cohort runtime.

EDF payload/header authentication, physical calibration, clock adjudication,
annotation completeness, independently verified fitting, competent reference
performance and protected participant delivery remain unresolved. This component
does not add arbitrary candidate, direct-observation, viewer or cross-cohort
transfer conditions. `scientific_qualification` remains `unknown`.
