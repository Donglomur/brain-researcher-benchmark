# Source SVM reward decoding: recovered protocol and paired point metrics

The [version-specific author archive](https://zenodo.org/records/19331923)
`s9_ML.zip` was recovered and its published whole-file MD5 verified. Only four
text source members were decoded. CSV observations and MAT results were not
opened. `SOURCE_PINS.json` records the exact source identities and metadata
census; it does not contain outcomes or local operator paths.

This component implements complete-region, identity-matched binary decision
metrics for the original single-unit reward task. It separates reproduction
error from improvement delta, keeps accuracy, sensitivity, precision and F1,
and preserves equal-unit weighting. It creates no split, fits no model and
does not certify an empirical result. The existing `full-reconstruction`
implementation and its original F2/F3 endpoint are preserved separately.

## What the released code establishes

| Source | Recovered behavior |
| --- | --- |
| `DCN/DCNdecodingSVM.py` | Iterates source unit ordinals 1–1006. |
| `VTA/VTAdecodingSVM.py` | Iterates source unit ordinals 1–22. |
| Both Python scripts | Use CSV column 1 for the outcome; all remaining columns are input features. A label encoder is called. |
| Both Python scripts | Fit supervised `KBestSelector(best_k='auto')` to **all** trials and labels before splitting. PCA is commented out, although the saved `Selector` field misleadingly says PCA. |
| Both Python scripts | Request `train_size=0.1` and a wall-clock integer seed; scale using the training subset; fit a default HappyML SVM. The hyperparameter-search execution is commented out. |
| Both Python scripts | Compute single-split metrics and separate ten-fold metrics. Ten-fold evaluation receives the selected full `X`, not the training-scaled split tensors. HappyML determines the hidden helper details. |
| `A02_Read_decoding_outcome.m` | Loads DCN result files, naturally sorts unit names, and uses the non-`k_` Accuracy/Recall/Precision/F_score fields. Arithmetic means weight units equally. Its first plot shows accuracy, recall and F1. The VTA glob is commented out. |
| `README_ML.txt` | Defines 1 as reward and 0 as no reward; identifies each CSV row as a trial. Refers to earlier deposit records, so the archive's verified record pin governs this inspection. |

These code facts refine the [article Methods](https://www.nature.com/articles/s41467-026-75371-4)
section on machine-learning reward codes. The Methods' single-unit temporal
input definition governs interpretation; the README's loose use of
“population” does not authorize pooled population inputs. Source Gaussian
kernel parameters, time coordinates and conversion from spikes to these CSV
features were not found in the four inspected source members.

The all-label feature-selection step exposes nominal test outcomes during
preprocessing. A reproduction must disclose and preserve that source
information condition. A split-first selector would be a scientifically useful
extension, but is a different preprocessing protocol. Scores from the source
pipeline must not be described as performance on an untouched holdout. An
improvement comparison requires a separately reviewed, matched access protocol
that resolves this exposure; this component does not silently grant candidates
test outcomes or claim generalization.

## Executable metric component

`score.py` uses Python standard-library arithmetic and exact source unit
censuses. Invoke it with three separately frozen JSON packets:

```sh
python3 -I -B score.py --reference OPERATOR_TEST.json \
  --candidate CANDIDATE_DECISIONS.json --author AUTHOR_DECISIONS.json \
  --output FRESH_OPERATOR_REPORT.json
```

The reference has keys `schema`, `region`, and `units`; its schema is
`cerebellar-source-test-v1`. Region is `DCN` or `VTA`. Each unit has `unit_id`
(an integer source ordinal) and `trials`. Each trial has a nonempty opaque
`trial_id` string and integer `reward` 0 or 1. Candidate and author packets
instead use schema `cerebellar-decisions-v1` and trial key `decision`. All three
packets require the complete region inventory and exactly matching per-unit
test identities. Input ordering may differ. No trial or unit may be dropped,
duplicated, pooled across regions, or matched by row position alone.

The operator must establish real trial identities, source membership, label
meaning, packet provenance, candidate freeze and reference custody before this
API is used. Files are parsed as ordinary trusted local JSON; this is not an
untrusted participant transport or containment layer. Targets and the detailed
report stay operator-private. The CLI rejects duplicate JSON keys, creates a
fresh output, and prints no target-derived detail.

For each unit the component computes TP, TN, FP, FN and the paper's binary
metrics. Primary DCN summary means weight each of the 1006 units equally, as in
the recovered MATLAB script. VTA is a separate 22-unit companion summary;
its link to a published figure aggregation is explicitly unverified. The
component never combines the regions or treats units as independent animals.

`improvement_delta` is candidate minus author on the same unit's test rows,
then averaged equally across units. `reproduction_mean_absolute_metric_error`
is the equal-unit mean of absolute per-unit differences, so positive and
negative reproduction discrepancies cannot cancel. These are separate point
metrics, not success thresholds or confidence intervals. Original F2/F3
reconstruction and SVM result reproduction remain different endpoints.

If a metric has a zero denominator, it is `null`; any regional mean containing
such a value is also `null`. This deliberately declines to invent the unknown
released HappyML/scikit-learn zero-division convention. It does not silently
exclude the affected unit. This case must be resolved against the pinned
source runtime before author parity is claimed.

## Remaining scientific work

- Pin the actual HappyML and scientific-library revisions; recover selector,
  SVM, split stratification/shuffling, cross-validation and scoring defaults.
- Recover original CSV time units/kernel preprocessing and animal/session
  mappings. Source integer unit ordinals are not biological replication IDs.
- An isolated operator must establish the original saved split/prediction
  support or an explicitly calibrated protocol-equivalent rerun. The scripts
  do not save the wall-clock seed or original row indices. Saved MAT results
  were intentionally left unopened in this source inspection.
- Bind the inspected DCN plotting route to Supplementary Figure 9, recover its
  published numeric comparator, and resolve VTA's publication role. No result
  values were inferred from filenames.
- Freeze matched access, resource budgets, uncertainty and meaningful effects
  before an improvement trial. Separate reproduction, source-protocol point
  improvement and current-SOTA claims.

`test_score.py` uses generated fixtures only, including full-census controls,
unequal trial counts, mismatched identities, negative deltas, and undefined
metrics. Test success establishes software behavior, not authentic preparation,
author inference, source reproduction, improvement readiness or a paper win.
