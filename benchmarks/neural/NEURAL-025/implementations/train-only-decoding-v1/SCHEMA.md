# Normalized operator input schema

All scientific inputs below belong to the trusted operator. A candidate agent
must receive only its permitted training inputs and evaluation neural/context
packet. These compound requests are not a public agent packet. Digests bind
declared content; they do not establish native source identity, rights,
pre-outcome freezing or protected execution.

`pipeline.py` accepts a UTF-8 JSON request. Duplicate keys and nonfinite JSON
numbers are refused. `dataset` and `protocol` are required. `score` additionally
requires `predictions`; `compare-controls` requires `context`. The expected
request, protocol and context digests come from an independently trusted release
or preregistration. Protocol/context hashes use UTF-8 JSON with sorted keys,
separators `(',', ':')`, `ensure_ascii=False`, and no NaN; `digest` implements this
encoding. Request-file hashes cover the exact file bytes instead.

## Dataset and protocol headers

Both objects contain:

| Field | Required value/domain |
| --- | --- |
| `schema` | Dataset `calcium_normalized_v1`; protocol `calcium_protocol_v1` |
| `task_id` | `NEURAL-025` |
| `author_commit` | `815b610b3beddfed5a3abf611d3a465ab9e4ce5c` |
| `joint_names` | Exact ordered 24-name `JOINT_NAMES` array exported by `pipeline.py` |
| `target_field` | `jointAngles` or `jointVelocities`, separate requests |
| `target_units` | Respectively `degrees` or `degrees_per_second` |
| `feature_variant` | `smoothed_deconvolved_events` or `radical`, separate requests |
| `event_conditioning` | `retrospective_public_liftTimeDLC` |
| `upstream_exposure_policy` | `processed_inputs_no_fold_safe_claim` |
| `sessions` | An array containing each of the ten exact session IDs once |

Angles and velocities cannot be concatenated into a 48-channel author endpoint.
Resampling to a 10 ms grid does not create 100 Hz independent observations.

Additional protocol fields:

| Field | Meaning |
| --- | --- |
| `condition` | `within_mouse` or `calibrated_new_mouse_local_baseline` |
| `metric_policy` | `train_sd_trial_session_mouse_macro_v1` |
| `recipe_selection` | `fixed_before_evaluation_no_data_tuning` |
| `window_ms` | Two strictly increasing integer endpoints, inclusive |
| `grid_step_ms` | Positive integer exactly dividing the endpoint difference |
| `cell_budget` | Positive integer, identical across sessions |
| `pca_components` | Positive fixed rank, no larger than budget or training rows minus one |
| `ridge_alpha` | Finite nonnegative scalar, required explicitly |
| `limits` | Positive integer `max_total_timepoints`, `max_rois_per_session`, `max_trials_per_session` |
| `new_mouse_cases` | Empty for within-mouse; five explicit cases for local calibration |

The recommended fixed recipe is in [README.md](README.md). Other explicitly
bound parameter values are construction configurations, not automatically new
scientifically admitted benchmark variants.

## Session identities and provenance

Use these exact normalized identifiers:

| Mouse | M1 session | S1 session |
| --- | --- | --- |
| cfa17 | cfa17_20200825_172828 | cfa17_20200827_165724 |
| cfa19 | cfa19_20200820_143508 | cfa19_20200826_191222 |
| cfa20 | cfa20_20201114_194635 | cfa20_20201118_200612 |
| cfa22 | cfa22_20220605_182006 | cfa22_20220611_174801 |
| cfa24 | cfa24_20220727_160603 | cfa24_20220724_155906 |

Do not infer region from chronological ordering. Optogenetic animals cfaVG1 and
cfaVG4 are excluded. Dataset and protocol session records both contain identical:

- `session_id`, `mouse_id`, and `region` (`M1`/`S1`).
- Ordered, unique `roi_ids`; these are session-local identities.
- `native_neural_field`: `data` for smoothed deconvolved events, `radical_rates`
  for the RADICaL track. A kinematic field cannot be relabeled as neural input.
- `upstream_temporal_support_ms`: two integer endpoints covering the entire
  decoder window. RADICaL must conservatively include at least[-200,+900]ms.
- Lowercase64-character `source_asset_sha256`, `clock_evidence_sha256`,
  `feature_provenance_sha256`, `normalization_recipe_sha256`,
  `upstream_exposure_sha256`, and `trial_selection_policy_sha256`.

These records must identify the exact original asset, syncTime/cycleDurMs/ROI-lag
handling, calcium representation, smoothing/resampling/kinematic-unit recipe,
upstream fitting/support exposure and original eligibility/exclusion policy.
This version compares their declared fingerprints and temporal bounds. It does
not read those native evidence bodies or certify their correctness.

The protocol session additionally contains `all_trial_ids`,
`training_trial_ids`, `evaluation_trial_ids`, and `trial_census_sha256` (the
canonical digest of the ordered `all_trial_ids` array). Training and evaluation
arrays must be nonempty, disjoint and partition the complete selected census.
No missing or unexpected trial is admitted. The exact original census and
exclusion evidence remain an external native-admission requirement.

The dataset session additionally contains `trials`, each with:

```json
{
  "trial_id": "the-original-trial-identity",
  "neural_trial_id": "the-original-trial-identity",
  "target_trial_id": "the-original-trial-identity",
  "neural_time_ms": [-10, 0, 10],
  "target_time_ms": [-10, 0, 10],
  "neural": [[0.0, 1.0], [1.0, 2.0], [2.0, 3.0]],
  "targets": "replace with a T-by-24 numeric array"
}
```

This is a shape illustration, not an admitted fixture or the recommended 51-point
window. Both time arrays must exactly equal the complete inclusive protocol grid.
Neural matrices have shape time-by-session-ROI-count; target matrices have shape
time-by 24. All values are finite real numbers. Booleans, complex/object arrays,
oversized integers that would lose identity in float64, ragged arrays, missing
times and positional neural/target trial mismatches are refused. No imputation,
resampling, cropping or masking occurs during fitting/scoring.

## Local-calibration condition

For `calibrated_new_mouse_local_baseline`, each `new_mouse_cases` record names
one of the five unique `heldout_mouse` values, the other four
`development_mice`, `transfer="none_session_local_calibration_only"`,
`calibration_label_access="declared_training_trials_only"`, and
`calibration_trials`, a mapping from its two session IDs to their exact protocol
training-trial arrays. All five cases are required. Development-mouse data do
not tune this fixed recipe; these records express the outer separation and the
explicitly permitted local calibration access. This baseline does not learn
shared neuron identities, transfer weights or an automatic new-mouse budget.

## Predictions and control context

`predictions` is a mapping from each exact session ID to a mapping from each
evaluation-trial ID to a complete time-by 24 numeric array. Missing/extra
sessions or trials, malformed shapes and nonfinite values are rejected.
Training and evaluation membership cannot be changed by a candidate prediction.

Control context has `schema="calcium_reach_context_v1"`, `task_id="NEURAL-025"`,
`event_conditioning="retrospective_public_liftTimeDLC"`, and ten `sessions`.
Each session has `session_id`, the protocol's `source_asset_sha256`,
`native_target_mapping_sha256`, and all selected `trials`. Every trial has
`trial_id`, unique nonnegative integer `original_trial_number` and
`reach_target="left"` or `"right"`. Native source LR values 1 and 2 mean left
and right respectively. The original trial number must survive filtering and
must not be replaced by the position of a filtered row. This experimental
direction and event phase must be public and equal across candidate/reference
conditions; future trajectories or target-derived surrogate fields are not
permitted predictor context.

The metadata-only split freezer uses no neural arrays or kinematic outcomes.
It returns complete source-ordered census/train/evaluation arrays to bind into
the protocol. The source checksum and mapping record still require independent
native validation before scientific use.

## Output and unsupported states

`fit-score` returns `metrics`, inspectable session `models`, complete evaluation
`predictions`, and explicit normalized-source execution scope. `score` returns
the metric record. `compare-controls` returns the fitted baseline, four complete
control results, paired descriptive comparisons and the exact within-target
rotation mapping/model states when supported. Undefined target scales and
constant-session R² remain explicit `null` outcomes. Unsupported control
support is labeled for the entire cohort, never scored on a surviving subset.

Every output retains authentic-input, native-clock, original-reference,
upstream-fit, protected-execution and scientific qualification limits. The
source verifier is inspection only and does not grant execution authority.
