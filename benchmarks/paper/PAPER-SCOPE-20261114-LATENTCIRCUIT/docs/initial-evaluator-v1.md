# Initial evaluator: fixed original-neuron prediction

This implementation turns the task's proposed improvement endpoint into a complete
owner-side arithmetic and admission module. It computes training-normalized
squared prediction error, a training condition-mean control and paired differences
in original neuron coordinates, and preserves both monkeys and every declared
eligible unit/condition/trial. It also emits development data and assessment
metadata as separate files. The source uses Python's standard library only.

It is not the empirical latent-circuit fitting pipeline or an activated task.
Authentic archive admission, full empirical reconstruction, behavioral
non-inferiority and protected candidate execution remain unresolved. The module
always returns `improvement_decision="withheld"` and
`scientific_qualification="unknown"`, including for perfect predictions. No task
registrations or historical specifications change.

## Source and interpretation

The authoritative [task](../task.json) is 15,797 bytes with SHA256
`b622f1c1fabd91722da8fd95e8179b4156c8f5b66bf35f7f2c8689fab13b241b`.
[Langdon and Engel's paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC11893458/)
uses two monkeys, 72 conditions and an empirical eligibility threshold of four
correct trials per condition. Its within-split preprocessing and fitted-subspace
metrics are reproduction semantics. The paper's projected fit does not measure
prediction of the entire original population.

The [pinned released class](https://raw.githubusercontent.com/engellab/latentcircuit/3e151da42379a0e659f3fefcdc858a66eba1eaac/latent_net.py)
has a two-term loss and lacks the complete empirical PFC objective/timing adapter.
The [pinned README](https://raw.githubusercontent.com/engellab/latentcircuit/3e151da42379a0e659f3fefcdc858a66eba1eaac/README.md)
demonstrates fitting to a trained RNN. This package does not guess the missing
procedure. It implements the registered prospective fixed-coordinate endpoint
with the new, explicitly defined weighting below. Neither that weighting nor the
minimum nested split is attributed to the original analysis.

[Provenance](../implementations/initial-evaluator-v1/provenance.json) records exact
source revision URLs, access limitations and rights. Source contents were read via
the web tool; direct terminal HTTPS requests failed. No unverified source-byte
checksum is claimed. This implementation is original code; no official source,
neural data or fitted parameters are vendored. The repository MIT declaration,
distinct Zenodo CC-BY metadata and UZH GPL3 page statement remain separate;
archive-specific rights have not been inspected.

## Input contract

The owner JSON uses exactly these top-level fields (unknown fields fail):

| Field | Meaning |
| --- | --- |
| `schema` | `latentcircuit.owner.v1` |
| `task_id` | `PAPER-SCOPE-20261114-LATENTCIRCUIT` |
| `policy` | `original-neuron-condition-balanced-train-variance-v1` |
| `frozen_program_sha256` | Lowercase SHA256 of the owner-frozen candidate artifact bytes |
| `data_provenance` | `dataset_id`, `owner_census_sha256`, `origin`, `preprocessing_description` |
| `time_axis` | `sample_centers_ms`, `reference_event`, `alignment_policy`, `native_join` |
| `conditions` | All 72 explicit stimulus-condition mappings |
| `units` | Complete declared original-unit inventory, including excluded units |
| `trials` | Complete declared single-unit trial ledger, including incorrect/excluded rows |

`origin` is `generated_engineering_controls` or `authentic_unadmitted`. Neither
value establishes scientific admission. The census hash is SHA256 of UTF-8
canonical JSON (`sort_keys=True`, separators `(',', ':')`, no NaN), with exactly:

```json
{"units":[["A","original-unit-id"]],"trials":[["A","original-unit-id","recording-id","trial-id"]],"conditions":["condition-id"]}
```

These example arrays are abbreviated: actual arrays contain all sorted unique
unit keys, trial keys and condition IDs. The unit/trial arrays are sorted
lexicographically. This binds the declared identity census; it cannot prove that
the declaration contains the whole authentic archive. The CLI separately requires
the owner-predeclared hash of the exact full input file bytes, binding labels,
roles, values and all other metadata. The owner must freeze these before candidate
assessment; the code cannot prove the chronology of a supplied hash.

Each condition has `condition_id` (unique string), `context` (`motion` or `color`),
`motion_level` and `color_level` (finite numeric coherence labels in the owner's
declared convention). The mapping must form exactly the complete two-context by
six-motion-level by six-color-level Cartesian product. This check does not
authenticate the native coherence encoding.

Each unit has `monkey` (`A` or `F`), `unit_id` and nullable
`original_exclusion_reason`. The original reason is retained in the audit ledger;
it is never a switch for dropping an otherwise eligible unit. Eligibility is
recomputed from at least four correct trials in every one of the 72 conditions.
The disputed published unit totals are not hardcoded or silently reconciled.

Each trial has exactly `monkey`, `unit_id`, `recording_id`, `trial_id`,
`condition_id`, `correct` (JSON boolean), `split` and `values`.
`split` is `train`, `validation` or `assessment`; incorrect trials also retain
their owner assignment. All eligible correct rows require 15 finite numeric
`values`. Other rows may have `values=null` to retain their original census
without fabricating activity. No boolean, NaN, infinity or missing sample is
accepted as a neural value. Values are already preprocessed neural trajectories
in an owner-declared common convention; normalization is performed by this
scorer. No spike binning, smoothing, PCA or clock conversion occurs here.

The `time_axis` supplies exactly 15 strictly increasing sample centers in
milliseconds and explicit reference-event/alignment-policy descriptions.
`native_join` must remain `unresolved`. The owner can exercise a prospective
grid, but cannot self-certify native equivalence through this interface. The
sample count follows the registered task; no assumption is made about the
unresolved first/last sample, temporal support or model resampling.

Trial identity is `(monkey, unit_id, recording_id, trial_id)`. A shared physical
trial `(monkey, recording_id, trial_id)` must have the same split, condition and
correctness across all units that name it. Recording identifiers must represent
real acquisition groups when known. The module never invents synchronized
population vectors from separately recorded units. Incorrect rows are retained
in the outer prediction interface but excluded from the correct-trial endpoint.
Requesting every outer row for eligible units avoids directly filtering outer
inputs by correctness. Error-trial mechanism analysis is
still a separate required native result and is not supplied here.

## Frozen prospective split and loss

The owner supplies the nested assignments before inspecting assessment outcomes.
Every eligible unit/condition requires at least two training, one validation and
one assessment correct trial. Validation may be used by the candidate for model
selection; assessment is owner-only. No rows are silently redistributed or
dropped to satisfy these minima. This single-inner-split implementation does not
claim a nested cross-validation ensemble. Other partitions require a future
explicit policy version, not an undocumented override.

For original neuron `u`, stimulus condition `c`, time sample `t` and training
trial `r`, let `y[u,c,r,t]` be the supplied value. Define the train-only center and
population variance:

```text
mu[u] = mean_c mean_r_in_train(u,c) mean_t y[u,c,r,t]
v[u]  = mean_c mean_r_in_train(u,c) mean_t (y[u,c,r,t] - mu[u])^2
b[u,c,t] = mean_r_in_train(u,c) y[u,c,r,t]
```

Each condition has weight 1/72 regardless of its trial count. All 15 samples have
equal weight. The variance uses a population denominator (`ddof=0`); there is no
epsilon, fitted test variance, PCA or candidate projection. Zero/nonfinite
training variance is an admission error and the original unit cannot be dropped.
This policy avoids permitting a candidate to increase its score by selecting an
easier latent projection or a test-dependent scale. It does not claim to be the
paper's variance estimator.

For prediction `p` and assessment trials, compute:

```text
loss[u,c] = mean_r_in_assessment(u,c) mean_t (p[u,c,r,t]-y[u,c,r,t])^2 / v[u]
loss[u]   = mean_c loss[u,c]
loss[A]   = mean_u_in_A loss[u]
loss[F]   = mean_u_in_F loss[u]
primary   = (loss[A] + loss[F]) / 2
```

The owner independently recomputes the same metric using `b[u,c,t]` as a
condition-mean control and reports candidate-minus-control differences per unit,
per monkey and equally over the two monkeys. Negative differences favor the
candidate on this neural endpoint. This is normalized squared error, not
projected R-squared, full-population explained variance, task-fit R-squared or
choice accuracy. No reduction-rank/native-latent comparator or equal-optimization
budget claim is made. No confidence interval is emitted: two animals, conditions,
units and initialization counts are not interchangeable biological sample sizes;
session/trial independence is unverified.

## Packets, predictions and commands

`prepare` emits separate development and outer metadata files. Development
contains eligible correct training/validation rows and values. Outer rows include
all correct and incorrect assessment trials for eligible units, and contain
only original identifiers and stimulus condition; the common metadata contains
the fixed units, condition mapping, time axis and artifact identity. It contains
no activity, correctness/choice/error annotation, excluded rows, fitted scaler or
reference diagnostics. The public packet hash excludes all assessment values and
private census metadata. Changing outer values leaves both public packets and
the training control unchanged.

This serialization boundary is not a filesystem sandbox. The owner must not mount
the owner JSON, reports or reference caches into candidate processes. Distinct
reproduction/improvement and code-access contexts still require an independently
qualified runner. IDs must be audited for hidden labels before release. The
owner-only full score includes training scales and per-unit errors and must not
be returned through an adaptive candidate feedback channel.

Packet completeness is not a proof that correctness cannot be inferred: the
eligibility and minimum correct-count constraints can reveal it in a small cell.
For example, a cell with a single assessment row and a required correct assessment
trial identifies that row's correctness. This residual count/inclusion inference
remains part of the protected-packet qualification hold; no privacy or protected
execution claim follows from this construction module.

Predictions use exactly `schema="latentcircuit.predictions.v1"`, `task_id`,
`coordinate_system="original_neuron"`, `packet_sha256`,
`frozen_program_sha256` and `predictions`. Each prediction has the five identity
fields emitted by the assessment packet plus `values` (15 numbers). Exact set
equality is required for every eligible original assessment row, including
incorrect trials whose correctness is not supplied to candidates. Only correct
trials contribute to the neural score. Duplicates,
missing/unknown neurons or trials, wrong conditions, changed dimensions, extra
scale/projection fields and learned-coordinate declarations fail. This cannot
detect a candidate that falsely labels projected numbers as original-coordinate
predictions; such numbers are still scored against the fixed original targets.

For example, in a separately configured owner workspace:

```sh
python3 /absolute/path/to/evaluator.py audit --owner /owner/owner.json --expected-owner-sha256 OWNER_FILE_SHA256 --output /owner/audit.json
python3 /absolute/path/to/evaluator.py prepare --owner /owner/owner.json --expected-owner-sha256 OWNER_FILE_SHA256 --output /candidate/development.json --assessment-output /candidate/assessment-inputs.json
python3 /absolute/path/to/evaluator.py baseline --owner /owner/owner.json --expected-owner-sha256 OWNER_FILE_SHA256 --output /owner/condition-mean-control.json
python3 /absolute/path/to/evaluator.py score --owner /owner/owner.json --expected-owner-sha256 OWNER_FILE_SHA256 --predictions /owner/predictions.json --candidate-program /owner/frozen-program.py --output /owner/score.json
```

Replace the placeholder path/hash with the owner-frozen files. Output parent
directories must already exist. Inputs and outputs must be distinct paths.
`baseline` generates an owner engineering control, not an authenticated candidate
execution; its artifact field binds the same assessment interface. `score` hashes
the supplied candidate artifact bytes, but does not prove that those bytes
generated the submitted predictions or were run under isolation. The code runs
no candidate program, model, optimization or data download. JSON errors return a
nonzero exit status; reports are finite JSON.

## Requirements and remaining gates

| Registered requirement | This package |
| --- | --- |
| Both monkeys, full original eligible population, 72 conditions | Strict declared-population audit; authentic census still unverified |
| Retain excluded units and reasons | Full derived eligibility ledger with original reasons; no drop flag |
| Nested disjoint trial splits, train-only preprocessing | Explicit train/validation/assessment audits and training-only scale/control; native preprocessing remains external |
| Fixed original-neuron neural prediction metric | Implemented with explicit prospective weighting and units |
| Condition-mean baseline | Implemented from inner training trials only |
| Original latent and low-rank equal-budget comparators | Held; neither fitted nor impersonated |
| 72-condition native train/test tensors and 200 starts per monkey | Held; no original split/fitting ensemble executed |
| Timing bridge, empirical objective/intercept and continuous behavioral guard | Held; no convenient alignment, binary substitute or invented tolerance |
| Projected fit, full variance fraction, suppression and error-trial outputs | Held; this scorer does not relabel its NSE as those metrics |
| Source population/rights admission and native reference | Held; original discrepancies and notices preserved |
| Private targets, fresh contexts and frozen programs | Packet separation and byte bindings implemented; protected runner/chronology/execution unqualified |
| Scientific qualification | Unknown; generated controls establish engineering behavior only |

The 22 generated controls cover analytic zero/unit errors, full condition and
animal weighting, training-only statistics under changed held labels, complete
prediction coverage, exclusion-ledger retention, shared-trial leakage,
projection/scale attacks, zero variance, nonfinite inputs, census/artifact pins,
incorrect-trial packet inclusion without scoring, and CLI safeguards. Run them
with the command in the package README. They use a
small synthetic two-monkey control with at most a few thousand trial rows and no
scientific fitting. The scientific empirical unit and benchmark count are
unchanged.
