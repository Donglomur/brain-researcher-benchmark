# Protected response scoring

This adds the missing numerical endpoint for the registered marmoset task. The
owner-side `score` function computes per-cell Pearson correlation against
repeat-averaged responses, full Poisson negative log likelihood on individual
repeat counts, paired candidate-minus-reference correlations, preparation
medians and an equally weighted descriptive summary of the two preparations.
It performs no file access, model fitting, smoothing, cropping or cell selection.

The existing `training-response` implementation, historical definitions and
current contracts are unchanged. This component is not an authentic data
preparation, baseline qualification, protected execution system, direct neural
interpretation task or complete benchmark. Integration into a participant
workflow still requires separate review and authentic source qualification.

## Source and endpoint

The task derives from [Modeling spatial contrast sensitivity in responses of
primate retinal ganglion cells to natural movies](https://doi.org/10.1371/journal.pcbi.1014157)
and original release [10.12751/g-node.t43ph1](https://doi.gin.g-node.org/10.12751/g-node.t43ph1/).
The cached author source at
[76b733421cc16131c2229e66a7714d8892de39d7](https://github.com/gollischlab/SpatiotemporalSCModel/tree/76b733421cc16131c2229e66a7714d8892de39d7)
supports the numerical target: `sc_model/scripts/run_sc_model.py` computes
`test_resp[:, temporal_crop - 1:].mean(axis=0)` at line 149, and
`sc_model/models/sc_model.py` calls `pearsonr(ground_truth, predicted)` at line 189.
The registration adds individual-repeat Poisson loss and preparation-aware
paired summaries. Those are benchmark endpoints, not claimed author results.

The original 170 classified cells and two named preparations remain mandatory:
51 OFF midget, 69 OFF parasol, 35 ON parasol, and 15 cells in the pooled large
OFF class. The scorer never guesses the split across preparations. These cells
were historically selected using WN/NM test reliability. Strict source-only
conditions restrict new fitting; they do not erase that historical exposure.
The two preparations have no established independent-animal mapping. Reports
contain neither population confidence intervals nor significance/pass claims.

## Calling the owner-side API

Load `scorer.py` with `importlib` or place its directory on the Python import
path. It uses Python 3.9+ standard-library facilities only.

```python
report = scorer.score(
    qualified_policy, protected_targets, sealed_candidate, frozen_sc_reference,
    policy_sha256=external_policy_identity,
    targets_sha256=external_targets_identity,
    candidate_sha256=external_candidate_identity,
    reference_sha256=external_reference_identity,
)
```

The four required identities use `fingerprint`: sorted compact ASCII JSON,
rejecting nonfinite metadata, with each bytes body replaced for hashing by its
byte length and SHA-256. Actual arrays must still be bytes, never substituted
descriptors. Identities bind all values and axis labels. They do not establish
source authenticity, independent evidence, freeze chronology or training access.
The owner must establish those properties externally. Freeze candidate and
reference before scoring, keep targets and reports outside participant access,
and do not provide repeated evaluator feedback to a live solver. This pure
function is not a process sandbox or a one-shot feedback broker.

The condition-matched reference argument must be a qualified spatial-contrast
model with the exact same allowed calibration policy as the candidate. A shared
policy hash detects mismatched declarations; it cannot inspect how either model
was actually trained. Reference architecture, calibration provenance and
competence remain external scientific obligations.

## Exact operands

The policy contains exactly:

```text
schema = marmoset-protected-score-policy-v1
task_id = marmoset-retinal-contrast-generalization
source_release = 10.12751/g-node.t43ph1
condition, training_policy_sha256, cohort_evidence_sha256,
complete_stream_census_sha256, rate_floor, coverage_policy,
preparations, streams
```

`condition` is one of the six existing training-adapter conditions. The target
domain is WN for `wn_to_wn`, `nm_to_wn_source_only`, and
`nm_to_wn_wn_assisted`; it is NM for the three remaining conditions. The
`training_policy_sha256` must identify the separately qualified corresponding
training/calibration policy. Mixed and assisted conditions stay distinct.
`rate_floor` is a positive finite expected count, frozen before test evaluation.
`coverage_policy` is exactly `all_cells_or_null`.

Each preparation is `{dataset, cells}`. Each cell is
`{cell_id, published_class}`. The two datasets are exactly those named in the
existing adapter; all 170 globally unique 32-hex cell IDs and the complete class
census are required. Per-preparation sizes are supplied by the authenticated
source join, never inferred from the class totals.

Each stream has exactly:

```text
stream_id, dataset, stimulus, seed, sequence_sha256,
repeat_ids, repeat_sequence_sha256, frame_ids, alignment_evidence_sha256
```

`stream_id`, cell IDs, frame/update IDs and repeat IDs are opaque 32-hex strings.
Lists are nonempty and unique; there must be at least two eligible updates.
`seed` is null for WN or integer 1/2 for NM. Each preparation has exactly one WN
stream or all externally authenticated NM streams for its target domain. A
policy cannot prove that an entirely omitted native seed exists; the complete
stream census must be independently authenticated. All declared streams are
required. Different seeds are never averaged together.

Every repeat's `repeat_sequence_sha256` must equal the stream's
`sequence_sha256`, in repeat order. Independent alignment evidence must verify
the actual repeated stimulus sequence, eligible update identity, response clock,
orientation and complete temporal context. These declarations alone cannot
prove those relationships. `frame_ids` must cover every eligible protected
update under one externally frozen, model-independent temporal-context rule.
The author code excludes the first `temporal_crop - 1` updates; this scorer does
not infer that crop, reselect it from targets, or silently truncate unequal
arrays. The owner must reconcile original timing and freeze the common complete
eligible support before model submission.

All bundles contain `schema`, `task_id`, `condition`,
`training_policy_sha256`, `unit`, and `streams`. Target schema is
`marmoset-target-counts-v1`; prediction schema is `marmoset-predictions-v1` and
also requires `model_sha256`. The unit is exactly
`spike_count_per_stimulus_update`, not Hz. Prediction packets have exactly
`stream_id`, `cell_ids`, `frame_ids`, `dtype`, and `values`; targets also have
`repeat_ids`. Identity orders must exactly match the policy. Stream packet order
may differ, because joins use unique stream IDs.

`values` is an immutable primitive bytes buffer in C order: target shape is
`[cells, repeats, eligible_updates]`; prediction shape is `[cells, eligible_updates]`.
Supported count dtypes are the existing adapter's integer 1/2/4/8-byte types and
float32/64, little endian (one-byte types use `|u1` or `|i1`). Counts must be
nonnegative, finite and integral; predictions may be nonnegative finite real
expected counts. Exact byte extent is required. Lossy integer-to-binary64
conversion, including a lossy repeat-count sum, refuses explicitly. No implicit
rate conversion, softplus, rectification, missing-value imputation or prediction
floor is applied to correlation.

## Aggregation and undefined values

Within each seed/stream, average the aligned individual repeats at each update.
For a cell's primary correlation, concatenate these separate stream means and
their matching predictions in the frozen policy order, so each eligible update
appears once. Repeat count does not weight correlation. Per-stream correlations
are also retained to expose between-stream effects. This concatenation rule is
an explicit implementation of the registration's "every eligible protected
update" endpoint; it is not a recovered author cross-seed aggregation claim.

Poisson NLL is `lambda - k*log(lambda) + lgamma(k+1)` on every individual
repeat/update, with `lambda = max(prediction, rate_floor)`. It includes the
factorial term. A stable Stirling-remainder form is used for counts at least 256
to avoid large-term cancellation. Cell and preparation Poisson summaries are
weighted by the actual number of individual observations; primary correlation
medians and the two-preparation macro summary have their separate specified
weighting. No repeat-noise interval is implemented.

Constant prediction or repeat-mean target gives `r=null` and an explicit reason.
Every cell stays in the report. A preparation's all-cell median is null if any
required cell is undefined for that metric. A paired delta is null if either
member is undefined. The equal-preparation summary is null unless both complete
preparation medians exist; it is the mean of those two medians, never a pooled
170-cell median. Class summaries use the same all-cell rule within preparation
and remain descriptive. All numeric domains, bodies and identities validate
before any report is returned.

`all_cells_or_null` is a conservative explicit software policy, not a change to
the canonical contract's still-unqualified primary decision. Scientific
enrollment must preregister and accept this coverage policy before authentic
test use. No advantage is assigned to undefined correlations.

## Verification and limits

`test_scorer.py` has 12 generated controls covering complete scope, individual
repeats, preparation weighting, undefined coverage, six conditions, seed
separation, missing/permuted support, units/calibration mismatch, invalid counts,
operand pinning, likelihood-only flooring, numerical scales and no file access.
Use the shared reviewed test pool during the parallel build. No original target
values, source arrays, predictions, private target paths or models are included.

The implementation is linear in the supplied numerical body size but has not
been profiled on the authentic panel. Per-cell lists and hashing temporaries
require separate resource admission. The source census, actual clock/crop and
seed identities, NM-only RF methods, competent baselines, target staging,
protected candidate execution and end-to-end qualification remain unresolved in
this component. It enables a concrete scoring operation once these inputs are
qualified; generated checks establish software behavior only. Native/direct
and viewer interpretation remain separate unavailable estimands. Tools/models
and frozen prediction programs may use this owner scorer only through a
separately protected workflow.
