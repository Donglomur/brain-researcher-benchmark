# NEURAL-025: prospective session-local calcium decoding

This component fits a decoder on explicitly declared training trials, predicts
the selected complete fixed windows of held-out trials, and scores all five
imaging mice and all ten M1/S1 sessions. It also computes phase and direction
comparators, a whole-trial shift diagnostic and descriptive paired mouse
uncertainty. It operates on **operator-admitted normalized data**. Native MAT
extraction, clock alignment, upstream calcium fitting, protected execution and
scientific qualification remain unverified.

The canonical [task](../../task.json) remains unchanged. This is a prospective
decoder and metric policy; it does not reproduce the author's full-session
selection, PCA, ridge-MML fitting or repeated cross-validation result. Source
derivations and exact code identities are in [PROVENANCE.json](PROVENANCE.json).

## Concrete recommended construction recipe

The primary construction recipe is **retrospective liftTimeDLC-conditioned
within-mouse readout from smoothed deconvolved events**:

| Choice | Explicit prospective policy |
| --- | --- |
| Population | cfa17, cfa19, cfa20, cfa22, cfa24; one source-listed M1 and S1 session each |
| Input | `smoothed_deconvolved_events`, source `neurons.data`; source smoothing SD 35 ms |
| Event/window | Public `liftTimeDLC`, -100 through +400ms inclusive on a 10 ms grid; no added predictor lags |
| Cells |100 per session, ranked by training-only feature variance, ROI identifier breaking ties |
| PCA | Training-centered, unscaled, fixed 90 components; this is 90% of cell count, not 90% explained variance |
| Regression | Fixed ridge penalty1.0 in **sum** squared-error units, unpenalized target mean; conventional prospective reference, not source MML or a claim of optimality |
| Split | One90/10 whole-trial split per session, stratified by left/right reach target, SHA256 ranking with seed240926; round evaluation counts upward |
| Target | Either 24 ordered `jointAngles` channels in degrees or24 `jointVelocities` channels in degrees/second, scored separately |
| Primary | Session RMSE divided by training target population SD; equal joints, two sessions and five mice |
| Secondary | SSE/SST R² **within each session/joint**, then equal sessions and mice |
| Uncertainty | Paired descriptive five-mouse bootstrap, retaining individual mouse differences; no significance/admission threshold |

The source supports the window, input, cell budget and dimensional budget. The
training-only variance selection, fixed ridge penalty, single deterministic
split, primary normalization and macro aggregation are explicit new choices.
They must be frozen before outcomes; the code verifies a supplied protocol hash
but cannot establish when that hash was chosen. The source uses an eligibility
predicate involving success, grab timing, lift reaction time, DLC quality, first
zone, movement/contact timing and `has_radical`. A source-matched cohort must
freeze that exact predicate and all exclusions. An alternative cohort requires
its own declared interpretation. No rows are silently excluded here.

`freeze_within_mouse_splits(context, expected_context_sha256=..., seed=240926)`
creates the specified split from original trial identity and public reach-target
metadata only. Each direction needs at least three eligible trials; at least two
remain for the training-trial rotation. The caller merges the returned lists
into the explicit protocol. These are selected complete fixed observation
windows, not a claim that every reach/grasp finishes by +400ms.

`calibrated_new_mouse_local_baseline` is separately supported as a **local
calibration comparator**. Each of five declared outer cases fits only the stated
calibration trials in its two session-local feature spaces. No parameters or ROI
identities transfer across mice. Calibration counts/access and all fitting
choices must be explicitly frozen; there is no default scientific calibration
budget, cross-animal transfer result or automatic qualification.

## Source and temporal distinctions

The author's `decode.m` performs PCA before cross-validation and independently
filters neural and kinematic `locked` masks before positional pairing. The new
admission requires matching original trial identities and exact shared temporal
support. Source `loadDecode.m` selects cells by stored full-session ZETA scores;
this component does not reuse those scores for its training-only selector.

`pca4Regression(0.9)` selects 90% of the input column count. The executable
cross-validation routine produces five repetitions of ten trial folds, despite
misleading parameter names. Its variance-explained statistic removes constant
residual bias and differs from the implemented SSE/SST R². These distinctions
prevent presenting this prospective reference as author-result parity.

The [version-of-record methods](https://doi.org/10.7554/eLife.106270.3)
describe calcium extraction, deconvolution, pruning and event-size scaling
before time locking. Train-only decoder fitting does **not** establish train-only
upstream calcium processing. Every session therefore binds an upstream exposure
record and an explicit upstream temporal-support interval. The emitted
upstream-fold-safety flag remains false. Symmetric smoothing and outcome-derived
lift conditioning support an offline retrospective interpretation, not causal
or online decoding.

RADICaL is a separate input track with `feature_variant="radical"` and
`native_neural_field="radical_rates"`. Its declared upstream interval must include
at least[-200,+900]ms, a conservative minimum implied by the methods' processing
window and padding. That requirement is not proof of actual model support:
native model provenance and the source's distinct output grids remain unverified.
The decoder output window alone is not the full neural observation budget.
Raw and denoised fluorescence are separate possible future tracks and are not
implemented by this component.

## Input and fitting interface

Use Python 3.11+ and NumPy 2.4.6. The module has no network, dataset download,
MATLAB, model checkpoint or fitting side effect on import. [SCHEMA.md](SCHEMA.md)
specifies complete normalized inputs, protocol and public control context.

```python
from pipeline import digest, run_pipeline, run_reference_controls

# Obtain expected identities from a separately reviewed, frozen protocol/context.
result = run_pipeline(dataset, protocol,
                      expected_protocol_sha256=expected_protocol_sha256)
comparisons = run_reference_controls(
    dataset, protocol, context,
    expected_protocol_sha256=expected_protocol_sha256,
    expected_context_sha256=expected_context_sha256,
)
```

The lower-level `fit_train_only` accepts training arrays only. Cell selection,
centering, PCA, target means and regression use those rows. Each session has its
own ROI space; equal column counts do not establish correspondence. A fixed
component count and ridge penalty are supplied explicitly; neither is selected
using evaluation inputs or targets. `predict` admits only the fitted ROI
identities. `model_record` exposes fitted state and its content digest for
training-state invariance controls.

`score_predictions` grades complete externally supplied predictions under the
same admitted protocol. It is an operator-side numerical interface, not a
protected candidate execution boundary. Evaluation labels must stay in the
operator's process; do not expose a scoring request or training/evaluation
compound dataset to a candidate agent.

## Metrics and controls

For each session and joint, average squared residuals equally across complete
evaluation trials and time points within each trial, then take the square root.
Divide by the population SD (`ddof=0`) of **training** targets. Average the 24
joint ratios, the two sessions per mouse, and then the five mice equally.
The normalization uses neither evaluation scale nor a candidate-selected scale.
Zero training SD makes that joint and the complete primary score undefined;
the code reports it without dropping any mouse, session or joint.

Secondary R² uses the same within-session trial weights and that session's
evaluation target mean. It then averages the two session results per mouse and
five mice equally. A constant evaluation target makes the corresponding result
undefined at every affected aggregation level. Between-session target offsets
therefore cannot inflate R². Stable scaled means/RMS calculations avoid silent
underflow of small nonzero targets or feature variances. Unrepresentable finite
arithmetic is refused explicitly.

`compare-controls` computes:

- A phase-only training mean trajectory on the identical public event grid.
- A direction-only training mean, constant across phase, for each left/right target.
- A stronger phase-by-direction training mean trajectory.
- A cyclic one-whole-training-trial rotation within each session and reach
  direction, ordered by original trial number, followed by the same decoder fit.

No control fits evaluation labels. The shift keeps full trajectories, direction
and phase marginals, and is one declared diagnostic rather than a permutation
significance test. Fewer than two training trials in either direction makes the
entire shift control explicitly unsupported; no partial-mouse score is emitted.
Missing training support for an evaluation direction similarly makes the
direction comparators unsupported on the complete population.

Paired uncertainty enumerates all 5^5 = 3,125 ordered five-mouse bootstrap resamples
of reference-minus-candidate NRMSE. It reports the individual mouse differences,
their mean and 2.5/97.5 percentiles using linear interpolation. The interval is
descriptive/exploratory with only five biological units. Repeated windows,
sessions and bootstrap draws are not additional independent animals. Undefined
mouse support propagates to an undefined comparison; no pass threshold or
coverage guarantee is claimed.

Metric records bind the actual admitted normalized neural/target float64 values,
shapes and trial/session identities in addition to the protocol identity.
Standalone paired summaries must match those inputs, target units, joint domain,
condition and complete biological support. These content identities still do
not authenticate original MAT files or prove a protected execution history.

## Commands and bounds

From the repository root, first inspect the current source identity using the
descriptor digest from a trusted reviewed release:

```sh
python3 -I -S -B benchmarks/neural/NEURAL-025/implementations/train-only-decoding-v1/verify_source.py \
  --expected-sha256 "$CALCIUM_SOURCE_DESCRIPTOR_SHA256"
```

A request contains `dataset` and `protocol`; `score` also needs `predictions`,
and `compare-controls` also needs `context`. Byte budgets are explicit caller
limits. The following shell variables are operator-chosen paths/digests/bounds:

```sh
python3 -B benchmarks/neural/NEURAL-025/implementations/train-only-decoding-v1/pipeline.py compare-controls \
  --input "$CALCIUM_REQUEST_PATH" \
  --expected-input-sha256 "$CALCIUM_REQUEST_SHA256" \
  --expected-protocol-sha256 "$CALCIUM_PROTOCOL_SHA256" \
  --expected-context-sha256 "$CALCIUM_CONTEXT_SHA256" \
  --max-input-bytes "$CALCIUM_INPUT_BYTE_LIMIT" \
  --max-output-bytes "$CALCIUM_OUTPUT_BYTE_LIMIT"
```

Input limits bound captured request bytes; protocol limits bound admitted array
rows, ROI count and trial counts. The result-byte check bounds emitted bytes
after serialization, not peak allocation/RSS. There is no preemptive CPU limit,
process isolation or complete native deployment capacity qualification. Output
goes to standard output only after success; refusals use a bounded diagnostic on
standard error and exit 2. Hash checks do not create data-use rights or establish
the origin of native scientific input.

Generated source controls run offline:

```sh
python3 -B -m unittest discover -s tests/construction -p test_calcium_pipeline.py -v
```

They verify independently calculated fits, complete-population scoring,
held-out perturbation invariance, malformed input rejection and control
semantics. They do not establish authentic neural decoding, source baseline
competence, uncertainty coverage or scientific qualification.
