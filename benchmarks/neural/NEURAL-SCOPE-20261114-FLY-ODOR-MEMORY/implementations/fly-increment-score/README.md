# Paired fly-level neural-increment scorer

`score.py` implements the registered point endpoint: nuisance squared error minus
neural-plus-nuisance squared error for the five-second mean goal-aligned speed,
averaged across eligible episodes within a fly and then equally across flies.
It reports genotypes separately, every fly effect, condition-specific scores,
and the complete supplied eligibility census. It rejects incomplete prediction
sets instead of dropping difficult or missing cases.

This component consumes evaluator-owned targets; it does not extract them from
the native archive. Physical odor offsets, heading/speed calibration, the 50/51
fly alias, complete source eligibility, model selection and uncertainty remain
unresolved. A successfully scored generated fixture does not qualify the task.
No authentic targets, predictions, model outputs or biological measurements are
included or opened by this implementation's tests.

## Numerical endpoint

For each eligible episode `e` of fly `f`, let `y[e]` be the target in mm/s,
`b[e]` the preselected competent nuisance prediction and `p[e]` its paired
neural-plus-nuisance prediction. The paired loss reduction is
`d[e] = (b[e] - y[e])**2 - (p[e] - y[e])**2`. The reported value for each genotype
is `mean_f(mean_e_in_f(d[e]))`, with units mm²/s²; larger is better. Each fly
contributes equally regardless of its episode count. No trial, bump, file, ROI
or frame is treated as an independent animal.

Primary summaries pool eligible primary episodes within each fly across that
genotype's conditions. Condition summaries repeat the same pairing and fly
weighting within each condition. The two genotype results are never combined.
No-odor and no-wind pseudo-offsets have distinct diagnostic roles and never
enter the primary score. Their authentic fixed schedules must be supplied by
the future target producer. Future re-encounter labels produce descriptive
strata only; changing them cannot change the primary result or eligibility.

All supplied ineligible episodes remain in the census with reason counts.
Reasons can overlap, so reason counts need not sum to the excluded count.
Flies with no eligible episodes have null losses and remain visible; they do
not receive an invented zero or enter the score denominator. A stratum with
no scored flies has a null score. Invalid or missing predictions fail the
entire evaluation before result creation. There is no imputation, clipping,
per-prediction omission, adaptive exclusion or data-dependent model selection.

## Evaluator input interface

All operands are private UTF-8 JSON. The CLI authenticates the bytes it reads
against externally supplied SHA-256 values before parsing; the maximum is
16 MiB per operand and 100,000 census episodes. Hashes bind a frozen selection,
but do not establish scientific source validity or training compliance. The
Python function `score()` assumes its caller has already authenticated the
parsed operands; use the CLI for file digest verification.

The target object has exactly these fields:

```json
{
  "schema": "fly-odor-evaluation-set/v1",
  "task_id": "NEURAL-SCOPE-20261114-FLY-ODOR-MEMORY",
  "target_definition": "mean_goal_aligned_speed_over_(physical_offset,physical_offset+5s]",
  "target_units": "mm/s",
  "evaluation_plan_sha256": "<64 lowercase hex characters>",
  "episodes": []
}
```

The empty list above illustrates the fields; an operand requires at least one
census episode. Each episode has exactly `episode_id`, `trial_id`, `fly_id`,
`genotype`, `condition`, `role`, `eligible`, `exclusion_reasons`, `target_mm_s`
and `future_reencounter`. IDs and condition names are nonempty strings.
`role` is `primary`, `no_odor_diagnostic` or `no_wind_diagnostic`; `eligible`
is boolean. An eligible episode has a finite numeric target and no exclusion
reasons. An ineligible episode has a null target and at least one unique string
reason. `future_reencounter` is true, false or null (unknown). Episode IDs are
unique across the evaluation set. A `fly_id` cannot span genotypes; a
`(fly_id, trial_id)` cannot span condition/role assignments. These consistency
checks do not resolve authentic identity aliases. Source completeness still
requires a reviewed archive-to-census bridge.

Each prediction object has exactly these fields:

```json
{
  "schema": "fly-odor-predictions/v1",
  "task_id": "NEURAL-SCOPE-20261114-FLY-ODOR-MEMORY",
  "arm": "nuisance",
  "access_mode": "frozen_program",
  "method_id": "<frozen reference method identifier>",
  "targets_sha256": "<digest of evaluator target file>",
  "evaluation_plan_sha256": "<same frozen plan digest>",
  "predictions": [{"episode_id": "<episode identifier>", "prediction_mm_s": 0.0}]
}
```

The other arm is `neural_plus_nuisance`. Each arm must contain exactly one
finite numeric prediction for every eligible episode, no ineligible or unknown
episodes, and match the target and plan bindings. Booleans are not numbers;
NaN, infinity, duplicate JSON keys/IDs and overflowed squared errors are errors.
The evaluator may attach target/plan digest metadata after collecting responses;
do not expose targets merely so a participant can construct this envelope.

`access_mode` is one of `direct_observation`, `typed_viewer`, `tool_assisted`
or `frozen_program`, and must match between the paired arms. Run each access
condition separately. Naming a mode does not implement its observation
transport, tool restriction, precommitment or feedback boundary. A frozen
program score is not evidence of direct or viewer interpretation. The same
scoring arithmetic can support the registered four matched modes once their
actual participant delivery and comparator conditions are qualified.

The evaluator's frozen plan must separately establish the complete source
cohort and alias map; physical offset and coordinate conversion; 95% coverage,
gap and circular-goal rules; source-derived diagnostic schedules; all
fly-grouped splits; validation-only nuisance selection; permitted histories;
normalization sensitivities and paired fly-level uncertainty/multiplicity.
This scorer does not infer those decisions from target values or method names.

## Run and verify

Python 3.11 and the standard library suffice. Keep operands and output outside
the repository in an evaluator-private directory. Invoke from this package:

```sh
python3.11 -I -S -B score.py \
  --targets /private/evaluation.json --targets-sha256 FROZEN_TARGET_DIGEST \
  --nuisance /private/nuisance.json --nuisance-sha256 FROZEN_NUISANCE_DIGEST \
  --neural /private/neural.json --neural-sha256 FROZEN_NEURAL_DIGEST \
  --output /private/new-score.json
```

The output file must not exist. It is created mode 0600 only after successful
validation/scoring. I/O failure can leave a partial file: retain the nonzero
exit status and do not treat file existence as completion. There is no retry,
overwrite, target feedback service, sandbox or protection from the same user
account. Results are evaluator-only and must not refresh candidate inputs.

Generated tests run with `python3.11 -I -S -B test_score.py` (through the shared
test pool during the construction wave). They independently hand-calculate an
imbalanced-fly example where pooled-episode scoring would give the wrong
answer, check genotype/control separation and descriptive-stratum invariance,
exercise complete-output failure, and test digest/private-output behavior.
These are numerical software controls, not author reproduction, scientific
neural-information evidence or participant performance.

## Provenance and remaining scope

The endpoint and boundary derive from this task's frozen `task.json` and
`understanding.v1.json`, which retain the reviewed paper/release/source audit:
[paper](https://www.nature.com/articles/s41467-026-75945-2),
[release](https://zenodo.org/records/20053990), and
[official code commit 371dc9d](https://github.com/nagellab/Kathmanetal2025/tree/371dc9de7a26edb0de4ee79b077a09283ac3a2eb).
This implementation reuses that recorded evidence; it does not claim a new
remote-source or native-data audit. Existing native-inspection and
pid-preparation code are preserved unchanged. `SOURCE_MANIFEST.json` records
their reference pins and this package's member hashes.

The target remains retrospective and conditional on released derivatives.
All-trial fluorescence normalization may embody later observations even when
direct histories end at offset. This score is not prospective causal
navigation prediction, physical displacement velocity, a causal neural
effect, or full-paper reproduction. It supplies point estimates and all fly
effects; no confidence interval, p-value, baseline competence or scientific
readiness is claimed.
