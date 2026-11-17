# NEURAL-026 measured prediction gain

This additive artifact scorer measures prediction of actual held-out joint angles. Its primary is gain over independently committed nuisance predictions. The original `delivery-source/private/score.py` remains unchanged and still grades reconstruction of a fixed analysis; that historical grade is separate.

The new scorer accepts any permitted prediction method. A candidate cannot increase the primary by deliberately worsening its own nuisance output: only the operator's independently frozen nuisance predictions enter the comparator. The arrays come from the original protected reference binding, joined to the same complete target identities and geometry.

For each mouse, area and joint, pool the five query folds once and compute

```
SST = sum((recorded_angle - pooled_query_mean)^2)
gain = (SSE_fixed_nuisance - SSE_candidate_prediction) / SST
```

Average the 24 joints equally, the two areas equally within each mouse, then the five mice equally. The complete panel is 50 computational cases, not 50 biological replicates. Negative gains and gains above one remain valid. Every prescribed joint requires positive pooled variance; an undefined joint invalidates the complete primary rather than disappearing from the average. Overflow, underflow or nonfinite arithmetic is refused; a nonzero residual may not disappear when squared.

The report preserves all 240 gains, candidate and fixed nuisance/neural/shifted MSEs, R², signed comparisons, five mouse values and descriptive S1-minus-M1 differences. There is no pass threshold, automatic improvement decision, p-value, causal claim or scientific qualification.

A positive gain means better prediction than this fixed nuisance learner. It does **not** identify neural dependence: an arbitrary candidate can also improve how context is modeled. A neural-information claim additionally needs matched candidate context-only and neural-disruption ablations under the same fitting/selection budget. The fixed author-style shifted comparator is useful context but is not that matched arbitrary-candidate ablation. The source observations include retrospective event duration and full coarse-motion trajectories; no online causal prediction is established.

## Candidate and operator interfaces

The new manifest schema is `neural026_understanding_submission_v1`, with exactly `schema` and `cases`. The 50 cases retain the original design order, case IDs and descriptors (`case_id`, `file`, `bytes`, `sha256`). Each `<case_id>.npz` contains exactly `trial_id` and `neural`, where `neural` is a finite float32/float64 array `(query_trials, 51, 24)` and `trial_id` matches the original complete ordered query IDs. The column name `neural` describes the declared prediction arm; it does not prove input dependence.

Legacy `neural026_submission_v1` artifacts with `nuisance`, `neural`, and `shifted` arrays are also accepted. Their candidate nuisance and shifted arrays are validated but never enter this new primary or its fixed-reference comparisons. They remain available to the unchanged legacy scorer for historical diagnostics. No candidate is required to recreate the author's algorithm for this endpoint.

All 50 candidate artifacts validate before the first protected target callback. They are captured and checked again against their admitted identities before use. The original source protocol enforces complementary train/query folds, once-only query support, five mice, two areas and matched declared target counts. These checks do not independently verify biological IDs, actual left/right counts, chronological fold assignment or authentic preparation; those remain operator provenance requirements.

The Python API is `evaluate(submission_folder, design, trusted_private_loader)`. The callback is an **operator-only** interface returning `(target, reference)` for a fixed case. It is not a participant tool. The reference must contain the independently committed nuisance, neural and shifted predictions, never values supplied by the candidate.

The command-line interface additionally requires expected SHA256 values for the complete operator design and protected binding:

```sh
python3 -B score.py \
  --submission /operator/candidate-artifacts \
  --design /operator/design.json --design-sha256 EXPECTED_DESIGN_SHA256 \
  --private-root /operator/protected-arrays \
  --binding /operator/binding.json --binding-sha256 EXPECTED_BINDING_SHA256 \
  --output /operator/new-grade.json
```

Use absolute paths without symlink ancestors. The binding retains `neural026_private_binding_v1`; every target/reference array must match its independently committed byte count and SHA256 before decoding. Hash agreement authenticates the selected bytes against the supplied pins; it does not establish that a candidate-chosen binding is trustworthy or that source data are authentic. The operator must obtain those pins independently of the candidate, commit the comparator before candidate outcomes and keep targets/reference arrays outside participant access. The complete installed source, including `DEPENDENCIES.json`, is likewise operator trusted.

The scorer reuses only pinned, unchanged original `protocol.py`, `common.py` and `array_io.py`. It does not execute a candidate or fit a reference. Missing authentic full ten-session inputs and protected references still prevent a real-data score; this addition does not provide a new participant runner, source preparation or scientific qualification.

## Verification and limits

`python3 -B test_score.py` exercises a generated complete 50-case panel, comparator-sabotage invariance, genuine target errors, signed gains, full admission before protected reads, target/reference alignment, undefined targets, extreme finite overflow and lost nonzero residuals, and CLI metadata/array tampering. `python3 -B review_test.py` supplies independent numerical controls, including a separately calculated pooled-variance oracle. These generated observations test implementation and failure behavior only. They are not neural data, model trials or neuroscience findings.

The source task remains the published five-mouse M1/S1 cohort associated with [GSK26](https://github.com/kaufmanlab/GSK26-public/tree/815b610b3beddfed5a3abf611d3a465ab9e4ce5c), [the source paper](https://doi.org/10.7554/eLife.106270.3), and [version-one data](https://figshare.com/articles/dataset/28326998/1). It overlaps NEURAL-025; this new scorer is a revised endpoint for NEURAL-026, not another dataset or benchmark registration.
