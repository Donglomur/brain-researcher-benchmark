# NEURAL-016 prospective encoding-contrast evaluator

This implementation recomputes paired held-out nuisance/full predictions against
operator-private scalar neural responses. It supplies a functioning numerical
evaluator, complete population accounting, declared split/fit checks, participant
summaries, paired uncertainty and a bounded temporal alignment control. It is
**not an executed Brain Treebank baseline, native preprocessing pipeline, finished
benchmark, or scientific qualification**. No authentic neural data or model was
run during construction. All generated fixtures are engineering controls.

## Scientific contract and source boundary

The immutable `task.json` (SHA256
`ab8710a3ec322e86df18814b376f34c6b11910517dd4487fce807dcd767a5ac5`)
asks whether prespecified linguistic variables add held-out explanatory power
beyond speaker, acoustics, visual motion and word timing. Source identities remain
10 clinical participants, 26 recording presentations and 21 unique movies. This
task shares the `brain-treebank` source family with
`PAPER-paper-method-replacement-011`; they are not independent cohorts.

The [primary paper](https://arxiv.org/html/2411.08343v1), especially sections 3,
4 and A.8, describes word-aligned raw IFP responses, linguistic and audiovisual
features and a GLM analysis. Its 500 ms response window motivates one possible
processed response definition; this evaluator does not silently impose it on a
future protocol. The pinned author source is commit
`c54ba38eab7814538bc03b1b6d29a3f50f034e12`:
[feature list](https://raw.githubusercontent.com/czlwang/brain_treebank_code_release/c54ba38eab7814538bc03b1b6d29a3f50f034e12/features_list.txt),
[GLM entrypoint](https://raw.githubusercontent.com/czlwang/brain_treebank_code_release/c54ba38eab7814538bc03b1b6d29a3f50f034e12/run_glms.py), and
[GLM runner](https://raw.githubusercontent.com/czlwang/brain_treebank_code_release/c54ba38eab7814538bc03b1b6d29a3f50f034e12/glm_runner.py).
The entrypoint contains unresolved names and the runner a debugger breakpoint.
Neither establishes this task's required held-out reference. Speaker controls
come from the task/paper even though the feature-list file omits speaker identity.
This code was independently implemented, with no upstream source copied.
Upstream code licensing and media redistribution remain unresolved.

`source_manifest.json` preserves the canonical roster and original holds. Source
URLs were inspected through the browser; direct raw HTTPS retrieval failed TLS,
so no content-byte SHA is claimed for those remote source reads. The exact Git
commit remains pinned. No archive, media, recording or transcript was downloaded.

## Frozen prospective estimator

The task's phrase “incremental explained variance” does not uniquely specify
residual-variance EV versus SSE-based R². The operator must freeze `primary_metric`
as `delta_explained_variance` or `delta_r2` before outcomes. Both are always emitted:

* EV = 1 − Var(y − prediction) / Var(y), with population variance.
* R² = 1 − SSE / sum((y − mean(y))²).
* Each increment is the full-model value minus its nuisance-only counterpart on
  exactly the same held-out rows. Negative values are retained.

EV ignores a constant prediction bias; R² penalizes it. A biased-perfect control
explicitly checks this distinction. Constant targets have undefined scores and
cause rejection with no silent deletion. Constant nuisance predictions are valid
mean-predictor controls and are flagged. Full constants are flagged under `report`
or rejected under `reject_full`, as frozen in the recipe. Nonfinite inputs,
residuals and final metrics are rejected.

First compute one contrast per fold/participant/electrode/continuous block.
Average blocks equally within each participant/electrode; average electrodes
equally within participant; finally average participants equally. These weights
are a prospective recipe choice, not a claimed author estimator. All declared
rows of a scored block must be evaluated together in one fold. Word and electrode
counts never become independent participant counts. The 95% percentile bootstrap
resamples participant-level *paired contrasts*, using a frozen seed and repetition
count. For one participant, intervals are absent. These intervals describe the
selected clinical cohort and do not resolve common-stimulus dependence, clinical
selection, or population generalization.

## Operator interfaces

The package requires an existing Python 3.10+ runtime with NumPy. It does not
install dependencies, download data or call model services. Run from the repository:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  benchmarks/neural/NEURAL-016/implementations/initial-evaluator-v1/evaluator.py \
  --protocol /operator/frozen-protocol.json \
  --private-targets /operator/private-targets.json \
  --submission /operator/paired-predictions.json \
  --output /operator/private-score.json
```

Paths in the example are placeholders. Protocol, private targets and predictions
are separate JSON files. Output is operator-private evaluation material; do not
return it as adaptive feedback. `tests/test_evaluator.py::packets()` is a complete
generated example of all three packets; its dummy pins, electrodes and exclusions
must never be used as authentic source evidence.

The protocol schema is version 1 and accepts these fields only:

| Field | Required content |
|---|---|
| `task_id`, `protocol_id`, `schema_version` | `NEURAL-016`, an explicit identifier, `1` |
| `frozen_before_outcomes`, `data_scope` | `true`, `public_development_only` |
| `recipe` | Explicit estimator, response definition/window, nonpositive feature lags, symmetric guard, training-only preprocessing and anatomy selection, person/movie split, nuisance/linguistic feature names, constant policy, bootstrap seed/repetitions |
| `source_files` | Role, identity, positive byte length and lowercase SHA256 for selected neural/timing/transcript/electrode payloads or their complete pinned manifests |
| `population` | Every one of the 26 canonical recording IDs, each included or excluded with a frozen reason |
| `blocks` | Unique block ID, canonical recording ID and nonoverlapping continuous time bounds |
| `rows` | Unique row ID, canonical participant/movie/recording IDs, electrode ID, block ID and time in seconds |
| `folds` | Unique fold ID, nonempty fitting row IDs and complete held-out block row IDs |

`recipe.nuisance_features` has four nonempty, nonoverlapping lists: `speaker`,
`acoustic`, `visual_motion`, `word_timing`. `linguistic_features` is separate.
`feature_lags_seconds` permits present/past features only. The symmetric
`guard_seconds` must cover the largest absolute feature lag and response-window
bound; all row times must lie that far inside their continuous block. This is a
conservative prospective support policy. Feature extraction must independently
verify actual source sample bounds and avoid reference indexing defects.

Every included recording must be represented; excluded recordings remain visible.
All declared rows must participate in a fold. Canonical subject/movie mappings
are checked. No fold may fit on its test participant, movie, recording or block;
repeated movie IDs across people therefore remain grouped for stimulus transfer.
The evaluator cannot discover omitted source words/electrodes, validate declared
exclusion reasons, or solve correspondence between different people's clinical
electrodes. Complete native payload inventory and cross-person output mapping
remain required before scientific use.

Private targets contain `protocol_sha256` and `values`, a list of `{row_id,value}`.
Submission contains the same protocol hash, `predictions` as
`{row_id,nuisance,full}`, and `fit_provenance` for every fold. Each provenance item
contains `fold_id`, exact `fit_row_ids`, `recipe_sha256`, and both
`nuisance_artifact_sha256` and `full_artifact_sha256`. The helper `canonical_hash`
computes SHA256 of sorted, compact JSON with nonfinite values forbidden.
Targets and predictions must cover exactly the held-out IDs once each. Unknown,
duplicate, extra or missing IDs are rejected. CLI output also records hashes of
the exact three input files, separately from semantic JSON hashes.

These checks verify *declared* provenance, not actual model execution. A hash is
not evidence that the associated fitting, feature screening, tuning or anatomy
selection avoided held-out information. The public protocol uses allowlisted
fields, but free text/identifiers could still encode targets; independent packet
release/privacy review remains required. Actual target values belong only in the
private target file.

## Autocorrelation control

`controls.joint_linguistic_circular_shift(times, linguistic_features, shift_steps,
minimum_displacement_seconds)` shifts every linguistic column together within
one uniformly sampled continuous block. It preserves circular discrete
autocorrelation and joint feature relationships, rejects irregular word timings,
identity/degenerate shifts and shifts below the declared minimum displacement.
It neither shifts neural outcomes nor crosses block boundaries. It must be
applied separately to frozen train/test blocks and followed by refitting the
entire frozen recipe. Native irregular word-event data need an independently
specified time-domain control; row-index rolling is not an acceptable substitute.

Optional `null_predictions` supply unique `permutation_id`, control name
`joint_linguistic_circular_shift_uniform_time`, `refitted_recipe_sha256` and a
complete paired prediction list. Each null also binds a per-block shift manifest
through `shift_manifest_sha256` and supplies complete per-fold `fit_provenance`
with fitted artifact hashes using the same schema as observed predictions.
Nuisance predictions and nuisance artifact hashes must remain identical.
The evaluator recomputes each null contrast and an add-one upper-tail rank.
It labels that rank **descriptive**, not a calibrated p-value. Stationarity,
conditional exchangeability given nuisance features, actual shifts/refits and
minimum displacement relative to the frozen feature support still require
external verification. Missing null predictions are explicitly reported.

## Verification and remaining gates

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s benchmarks/neural/NEURAL-016/implementations/initial-evaluator-v1/tests -v
```

Controls cover independently calculated EV/R² and negative increments, bias,
equal-unit aggregation, deterministic paired uncertainty, temporal and repeated
movie leakage, exact IDs, finite/constant behavior, malformed inputs, split-block
weighting, uniform-time circular autocorrelation and a real CLI round trip.
They establish bounded engineering behavior only. No native reference,
scientific claim, baseline competence or population qualification was measured.

All original holds remain: transcript/electrode pins and independent movie
confirmation; neural HDF5 shape/calibration/inclusion; reference path/indexing
repairs; code/media rights; clinical/electrode generalization; full packet hashes,
alignment and privacy; frozen complete fitting/resource/access protocol; matched
signal-derived reference; native scorer/reference replication and admission;
and protected evaluation beyond public development. The implementation does not
modify the canonical task, historical manifests, registry or qualification flags.
