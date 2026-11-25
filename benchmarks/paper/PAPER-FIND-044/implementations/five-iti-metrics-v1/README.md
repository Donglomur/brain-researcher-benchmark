# Five-ITI source metric arithmetic

This component corrects a consequential metric mismatch in the existing reward
programme. The shared `paper/runtime/models.py::compare_models` computes
`n * log(log_RSS / n)`. The original `calculate_aic.m` instead computes
`nAnimals * log(mean(raw_squared_residuals, omitnan)) + 2*k`.
The source separately uses natural-log RSS to select each family's parameters.
This implementation preserves those two ordered operations.

The existing shared implementation and registered 60/600-second reconstruction
are preserved. This is a task-local replacement component for integration, not a
new benchmark registration or a claim of original-paper improvement.

## Executable interface

`score.py --input NUMERIC_EXPORT.json --output NEW_RESULT.json` uses Python's
standard library only. It never launches simulations or fits a new model.
`--output` must be a new path; omitting it writes JSON to stdout. Input/output
files with authentic observations must remain outside the repository.

The input is a JSON object containing:

- `schema`: `reward-five-iti-model-scores/v1`.
- `conditions_s`: exactly `[30, 60, 300, 600, 3600]`.
- `prediction_stage`: `after_source_filtering_and_censoring`.
- `behavior_trials_to_learn`: a nonempty rectangular matrix with five columns.
  These are the author's column-wise animal observations, in trials. Rows are
  storage positions, not evidence that the same animal occurs across ITIs.
  `null` represents the source's NaN padding/missing observation. Every ITI must
  retain at least one observed animal; the full original roster still needs an
  authenticated preparation manifest.
- `families`: objects with a unique `name`, nonnegative integer `num_parameters`,
  and a nonempty ordered `candidates` list. Each candidate has a unique `id` and
  `trials_to_learn_by_iteration`: twenty rows by five ITI columns. Tensor order
  is source order after family filtering. Values are positive finite numbers
  or `null` for the source's missing/censored value.

The tensor is the transpose of one source candidate's five-ITI by twenty-repeat
slice. Arithmetic means are taken over the twenty iterations **before** log
transformation. A single missing iteration propagates to that ITI mean, matching
`mean(TTL,3)` without `omitnan`. Simulations are not biological replicates.
When dividing a positive finite onset by twenty enters the binary64 subnormal
range (including zero), an exact-rational fallback preserves the representable
arithmetic mean. Normal divided terms keep the existing reduction, and missing
iterations still propagate.

The output retains every candidate's natural-log RSS, raw MSE, unpenalized AIC,
parameter-penalized AIC and source corrected-AIC expression. Selection ranks
use only log-RSS, with ties preserving source order. The source's first-ranked
candidate is retained even if every RSS is infinite; `selected_id` is null in
that case so the diagnostic cannot imply a usable fit. The supplied family list
is not independently authenticated as the complete source comparator panel.

Source `nAnimals` counts nonmissing behavioral cells. Raw MSE omits NaN
residuals, including those caused by a missing model prediction. These counts
can disagree: both are reported, and missing predictions produce infinite
selection RSS and incomplete support. A perfect fit retains negative-infinite
AIC. Nonfinite numbers are serialized as the strings `NaN`, `Infinity` and
`-Infinity`; they are never substituted with zero. Corrected AIC's source value
is retained even outside `n > k+1`, with an explicit sample-size flag.

The source reports `k=0` and penalties ANCCR=5, microstimulus TD=8,
IRI-scaled microstimulus TD=8, constrained SOP=12 and unconstrained SOP=12.
The caller supplies the penalty to allow a future candidate's declared model
complexity; this component does not authenticate that declaration.
Cross-family relative likelihoods are not computed here: the source's `k=0`
reference minimum excludes ordinary microstimulus TD while still calculating
its relative likelihood. That separate source reporting convention must be
preserved explicitly during full baseline replay.

## Discriminating control

For generated behavior `[1,100,10,10,10]`, model A predicts
`[2,100,10,10,10]` and model B predicts `[1,110,10,10,10]`.
Model B has lower log-RSS, while model A has lower raw-scale AIC. The tests
assert both outcomes using independent closed-form expectations. They also
exercise unequal animal counts, source NaN behavior, mean-before-log order,
missing simulation iterations, stable ties, degenerate AIC/AICc, all-five-ITI
coverage, identity/domain rejection and the executable JSON interface.
These invented numbers are software controls, never paper observations.

## Source and preparation limits

The implementation is based on author revision
`b7687eba02128049eb50f8a13a7201443e180a21`:

- [calculate_rss.m](https://github.com/namboodirilab/duration_between_rewards_controls_learning_rate/blob/b7687eba02128049eb50f8a13a7201443e180a21/CODE_simulations/functions/calculate_rss.m), lines 9–16.
- [calculate_aic.m](https://github.com/namboodirilab/duration_between_rewards_controls_learning_rate/blob/b7687eba02128049eb50f8a13a7201443e180a21/CODE_simulations/functions/calculate_aic.m), lines 8–15.
- [behavior_fit.m](https://github.com/namboodirilab/duration_between_rewards_controls_learning_rate/blob/b7687eba02128049eb50f8a13a7201443e180a21/CODE_simulations/behavior_fit.m), the behavior-loading, simulation-mean, RSS-sorting and best-candidate AIC blocks.

Local cached original source bodies were inspected; no new source payload was
downloaded and no private historical answer/reference was accessed. Source
body hashes and the old implementation pin are in `SOURCE_PINS.json`.

This component accepts **post-preprocessing tensors**. It deliberately does not
claim to reconstruct the original cohort, censoring or native fit. In particular,
the source microstimulus branch finds threshold-exceeding `(row,col)` pairs and
assigns `tensor(row, i, col) = NaN`. MATLAB subscripting selects the Cartesian
product of the row/column index vectors; an elementwise Python threshold mask
would change that operation when multiple distinct pairs occur. This is a
static source finding requiring native parity and a recorded branch decision,
not evidence that it affected the published result. The source caps are
`[800,400,88,48,16]`; they must not silently be applied to other families.

The MATLAB RSS loop also uses `length(y_pred)`. This implementation evaluates
one prediction vector at a time and does not reproduce an out-of-bounds loop
for an artificial grid smaller than five. No native MATLAB execution or
bitwise numerical parity is claimed. The covered domain is positive finite
onsets plus source NaNs; zero, negative, infinite and complex values are rejected.

The full five-ITI animal roster and source summary mapping, original selected
model/baseline scores, simulation/censoring parity, uncertainty rule, meaningful
effect size, equal access/compute budgets and behavior/dopamine companion scope
remain unresolved. Consequently task/contract status is unchanged and every
result explicitly carries `source_preprocessing_authenticated: false` and
`paper_improvement_claim: false`.

## Integration proposal

Before any use of the shared `compare_models` as the original paper metric,
replace its log-RSS-derived AIC with the raw-scale formula and enroll the
ordering-reversal regression test. Do not amend historical numerical outputs.
This task-local component supplies that arithmetic and the five-ITI selection
path; shared code, registry, canonical task and contract edits are owned by
integration. Source acquisition and native author calibration require the
separate frozen operator protocol. This patch does not authorize either.
