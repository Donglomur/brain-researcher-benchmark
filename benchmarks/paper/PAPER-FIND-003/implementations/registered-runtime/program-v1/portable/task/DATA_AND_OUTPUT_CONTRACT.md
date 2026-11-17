# Long-input reconstruction and output contract v1

## Data and preprocessing

The active CSV is `dd_ripple_during_learning_raw.csv`, UTF-8, with literal columns `ripple,channel,subject,trial,ACC,phase`. Keep input order and assign one-based raw data-row IDs before any exclusion. Treat ripple and trial as binary64 numbers; channel/subject/ACC/phase are text. Phase names are stimulus, feedback and interval. `ACC` is recoded to 1 exactly for `correct`, 0 for `wrong`. No session, performance, sign, participant or contact selection is added. The supplied case is already the active input; do not choose a different deletion or sensitivity case.

For each phase separately, take strictly positive finite ripple values and their 99th percentile using Hyndman–Fan type 5: sorted position `n*0.99+0.5`, clamped to endpoints, linear interpolation otherwise. Mark source99 exclusions by strict `ripple > threshold`; ties remain. Recompute thresholds from the active input. Remove marked raw rows. Unstack ripple by phase with grouping columns in exact source order `channel,subject,trial,ACC,exclude`, where retained exclude is false. Group tuple order is first occurrence in retained source order. Wide IDs start at 1 in that order. Phase columns are sorted by name (`feedback,interval,stimulus`); models address names. Default duplicate-cell reduction is numeric sum with missing-value propagation, not mean or omit-missing. The qualified active domain has unique raw cells and no missing group/phase keys; if unsupported source structure occurs, abstain rather than invent a mapping.

Absent phase cells become missing in the wide table. Select finite response cells separately for each phase; do not delete a wide row because another phase is missing. Keep original wide IDs for membership digests. Canonical wide CSV columns are `channel,subject,trial,ACC,exclude,feedback,interval,stimulus`, comma CSV quoting as needed, LF row endings, UTF-8 without BOM. Numeric values use Python binary64 `str` spelling, integers use integer spelling, false exclude is `0`, missing cells `NaN`. This byte convention is an adapter identity, not a claim of historical MATLAB row-order or byte identity. The provided `derived_wide_sha256` identifies that operator canonical table; never substitute the raw hash. An alternative implementation may fit an equivalent in-memory representation and report the provided identity, while mapping support to the same canonical wide IDs. It need not physically serialize a Python-spelled CSV. The developer positive reconstructs those exact bytes as its own check; the artifact scorer cannot certify that hash computation occurred.

## Model and numerical units

For each phase use `RippleRate ~ ACC * trial + (1 | subject/channel)`: numeric ACC and raw, uncentered trial; subject intercept plus intercept for each subject–contact pair, even when contact labels repeat across subjects. Four named fixed terms are `(Intercept),ACC,trial,ACC:trial`. Fit REML with unit weights and zero offset. The bounded reference uses lme4::lmer, bobyqa, maxfun 10000, restart_edge false, derivatives on and rank-deficient fixed design rejection, one optimization per phase. Do not turn this reconstruction into optimizer selection or a method search. Equivalent parametrizations must be transformed back into this declared basis, including the full covariance on both axes.

Ripple rates retain their released stored rate units. Intercept and ACC difference have rate units; trial and interaction have rate per raw trial. Variance components are absolute squared-rate units, not relative theta or standard deviations. Covariance entries carry the product of the associated coefficient units. Signed candidate-minus-reference errors are preserved. Wrong/correct trial slopes are beta_trial and beta_trial+beta_interaction; their variances use the full covariance, including cross terms. No p-values, confidence intervals or significance criteria are requested. The optional objective is separate from the original-scale model diagnostics.

## JSON wire format

All objects have exact fields; no duplicate keys, booleans as numbers, NaN/Infinity, overflow, nonzero-to-zero literal underflow or extra fields. Ordinary binary64 rounding is allowed. Integer JSON tokens are limited to 18 characters including a minus sign; larger finite magnitudes may use decimal or exponent spelling. Text/reason strings are limited to 512 characters, keys to 96 characters, and nesting to 12 levels. Source IDs are integers, not floats. Source lists may be permuted; comparisons use identities, not their order.

Outer keys: `schema_version` (1), `task_id` (`PAPER-FIND-003`), `mode` (`long_input_reconstruction`), `input_raw_sha256`, `preprocessing_spec_sha256`, `derived_wide_sha256` (matching public identity), `submission_status` (`complete`, `partial` or `abstained`), `preprocessing`, `model_artifact`.

For complete or partial reports, preprocessing is exactly:

```json
{"phase_source_row_ids":{"stimulus":[],"feedback":[],"interval":[]},"source99_excluded_row_ids":[]}
```

Populate the four lists so every active raw ID occurs exactly once. Every retained raw row belongs to its phase, including the phase-specific missing-cell consequences of exclusions in other phases. A reported phase's support digest is SHA256 of ascending retained canonical wide IDs, each decimal ID followed by LF, encoded ASCII. Support counts are n_obs, distinct subjects and distinct subject–contact pairs in that phase's finite-response frame. The evaluator compares all raw IDs against its fixed partition and support; wrong but complete partitions are scored separately from numerical error. Omitting difficult rows cannot shrink the denominator.

`model_artifact` has exactly `schema_version:1`, `task_id`, `input_sha256` equal to the derived-wide hash, `submission_status` matching outer status, and `models`: three unique phase objects, in any order. Each has `phase,status,reason,fit`. Reported status has reason null. Abstained status has a nonempty bounded reason and fit null. A complete report has three reported phases; partial has one or two; whole abstention has none and outer preprocessing null.

Each reported fit has exactly:

- `coefficients`: the four named finite numbers in the stated basis.
- `covariance`: `axes` listing the four terms once and `values` a finite 4×4 matrix in that axis order.
- `variance_components`: finite `subject,nested_contact,residual` absolute variances.
- `support`: integer `n_obs,n_subjects,n_nested_contacts` and lowercase `row_ids_sha256`.
- `method`: `estimator` REML/ML/other; `random_effects` subject_plus_nested_contact/subject_only/contact_only/pooled_contact/other; `weights` unit/other; `offset` zero/other. These are claims compared separately, not evidence of actual program behavior.
- `reml_diagnostic`: null, or `criterion` finite and `convention` either `lme4_profiled_REML_original_design_including_constants` or `other`.

The numerical comparison retains fixed expected denominators of 12 coefficients, 48 covariance entries and 9 variance components, plus all phase contrast/covariance diagnostics. Partial coverage is explicit, never normalized only over a submitted favorable subset. Derived arithmetic outside supported binary64 range is marked unsupported rather than silently becoming zero/Infinity. There is no blended scientific-success reward, tuned separation threshold or automatic improvement claim.
