# NEURAL-040 initial evaluator

This additive implementation supplies an executable matched encoder and a separate
held-out scorer for the frozen task **Audio, visual and language contributions to
fMRI**. It consumes precomputed feature matrices; it does not acquire media, run a
language model, download neural payloads, or claim an authentic reproduction. All
results produced so far are generated engineering controls. Scientific qualification,
protected assessment, native baseline reproduction and source-payload admission
remain false/unresolved. The canonical task and historical source remain unchanged.

The package is in `../implementations/initial-evaluator-v1/`. Python 3.11 and NumPy
are sufficient; no install or network connection is required at execution time.

## Scientific contract and prospective recipe

The task requires held-out correlation differences, parcel deltas, person summaries,
matched controls, whole-film splits, fixed language features and numerical-claim
verification. The [pinned organizer repository](https://github.com/courtois-neuromod/algonauts_2025.competitors/tree/96750e7017b30cb02f011c11561a3df897695853)
specifies TR 1.49 s, four people (`sub-01`, `sub-02`, `sub-03`, `sub-05`) and 1000
parcels per person. These identities and counts are mandatory.

The [organizer challenge](https://algonautsproject.com/2025/challenge.html) distinguishes
ID scoring, which pools episodes, from OOD scoring, which correlates each film
separately and averages parcels, films, then people. This task asks about a different
film, so `equal_film_pearson` is the explicit prospective estimator. Guarded segments
and repetitions of one film are concatenated **within that film**, then Pearson r
is computed for each parcel. Films, parcels and people each receive equal weight
at their respective level; rows are never biological replicates. Negative correlations
are retained. Constant/nonfinite targets or predictions reject the packet instead of
silently removing parcels. The pinned OOD scorer has native `[5:-5]` segment trims;
this implementation instead requires an explicit lag/context-aware guard. Its result
must not be presented as the native organizer score without independent qualification.

The numerical recipe is a new, prospective reference: `full`, `no_audio`, `no_visual`
and `no_language` independently standardize their available lagged features using
training rows only, then fit training-only PCA and retain the same fixed rank `k`.
Retained PCs are whitened so `Z.T @ Z = n_train I`; every arm uses the same positive
ridge alpha and unpenalized intercept. Thus within a person all arms have `k` readout
columns and effective degrees of freedom `1 + k*n_train/(n_train + alpha)`. Insufficient
rank rejects the recipe. This matches the feature bottleneck and readout capacity;
it does **not** establish equal pretrained extractor capacity, exposure, cost or
representation quality. Those matched controls need qualification. There is no tuning
on held-out responses. The native baseline uses its own windowing and per-target
RidgeCV recipe; this package does not reproduce that fitting procedure.

Every segment carries a whole `film_id` (or whole episode identity for an episode
packet) and a `run_id`. No film may occur in both train and evaluation, including
repeated viewings. Feature contexts must be measured in TRs: the left guard covers
maximum lag plus left context, the right guard covers right context, and minimum
lag must cover right context so no predictor uses stimulus future relative to its
neural target. Metadata cannot establish that an external feature extractor actually
obeyed its declared context. Source-derived context/exposure validation remains a hold.

The paired null shifts each arm by the same frozen circular offset within each
evaluation segment, preserving within-segment circular autocorrelation and keeping
boundaries separate. Offsets must exceed the guard in both circular directions;
matching stimulus/run/length offsets synchronize across people. The reported tail
fraction is a descriptive diagnostic over the supplied finite shift set, **not a
calibrated p-value**, conditional unique-information test or multiplicity correction.
Stationarity, run mapping and exchangeability require scientific review. An exact
enumeration of all 256 ordered four-person empirical bootstrap resamples gives a
descriptive percentile interval; it cannot justify a general-population claim.

## Packet interface

`protocol.json` declares these required fields:

| Field | Meaning |
| --- | --- |
| `schema_version`, `task_id`, `data_scope` | `1`, `NEURAL-040`, `public_development_only` |
| `dataset_commit`, `participants`, `tr_seconds` | Exact organizer commit above, four-person order above, `1.49` |
| `estimator` | `equal_film_pearson` |
| `parcel_ids` | Person-keyed lists of 1000 unique native labels in array column order |
| `lags_tr`, `guard_tr` | Ordered distinct nonnegative lags, symmetric explicit boundary guard |
| `feature_context_left_tr`, `feature_context_right_tr` | Declared maximal context support for every supplied family |
| `capacity_rank`, `ridge_alpha` | Frozen common positive integer rank and positive finite penalty |
| `feature_assets` | `audio`, `visual`, `language`; each has `extractor_revision`, `checkpoint_sha256`, `context_policy` |
| `segments` | Ordered records below, including train and evaluation for every person |

Each segment has `id`, `participant_id`, `film_id`, `run_id`, `split` (`train` or
`evaluation`), `n_samples`, and `feature_keys` mapping all three families to NPZ keys.
Evaluation segments also carry `null_offsets_tr`, an equal-length ordered list of
predeclared integer offsets. All IDs are nonempty strings without `__`; IDs must be
source-derived in an authentic packet. Protocol construction and selected full-population
completeness require independent source validation before outcomes.

`features.npz` contains exactly the referenced keys, each a finite numeric
`(n_samples, n_features)` array; each family keeps a fixed column count. Training
targets and private evaluation targets are separate NPZ files keyed by exact segment
ID, with `(n_samples, 1000)` arrays. Wrong-split, omitted and extra targets reject.
Neither targets nor predictions accept pickle/object arrays. The scoring output is
evaluator-private and must not be supplied to an agent during protected evaluation.

Each target NPZ has a JSON sidecar: `protocol_sha256` is SHA256 of canonical compact
JSON (`sort_keys=True`, separators `(',', ':')`); `parcel_ids` repeats the exact ordered
map; `split` is `train` or `evaluation`; `npz_sha256` pins the actual file. These checks
detect declared mismatch/tampering, but cannot independently prove anatomical alignment
or truthful lineage. The fitting command has no private-target input. Prediction keys
are `arm__segment_id`, with `(n_samples - 2*guard_tr, 1000)` arrays in retained-row order.

```sh
python evaluator.py encode --protocol protocol.json --features features.npz \
  --training-targets training-targets.npz --training-target-metadata training-targets.json \
  --output-dir encoded
python evaluator.py score --protocol protocol.json --predictions encoded/predictions.npz \
  --prediction-metadata encoded/prediction-metadata.json --private-targets private-targets.npz \
  --private-target-metadata private-targets.json --output score.json
```

The encoder creates a new output directory with predictions, file hashes, protocol
hash, ordered parcel labels and per-person/arm fit accounting. The scorer recomputes
per-film/per-parcel r, modality-removal deltas, four person summaries, uncertainty and
paired shift diagnostics. Optional `--claims claims.json` accepts a list of
`{"family":"audio","mean_delta_r":0.1}` records (visual/language also supported),
checks each to absolute tolerance `1e-8`, and reports true/false. It does not grade a
favored biological conclusion. Unsupported, duplicate and nonnumeric claims reject.

The API functions `encode`, `score`, `validate_protocol` use the same implementation
as the CLI. Tests contain a complete generated packet constructor for interface
examples; its zero checkpoint hash and generated parcel labels are explicitly fake
engineering identities and must never be used as authentic asset evidence.

## Validation and remaining gates

Run `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` from the
package. Independent controls cover an analytic Pearson oracle, a two-film offset
counterexample, unequal-person recording lengths, train-only transforms, leakage,
future context, rank/capacity, malformed/constant outputs, parcel ordering, missing
IDs, paired-null identity, claim verification and CLI artifact tampering. They establish
engineering behavior only. No authentic cohort, native payload, model campaign, gated
model, protected target or external submission was accessed.

All canonical holds remain: anonymous annex access and HDF5/transcript schema; exact
full input and public/private packet hashes; parcel alignment and accessible features;
pretrained feature/model exposure and native baseline license/file qualification;
media rights; frozen selection/exclusion/access/resource/split/estimator protocol;
authentic signal-derived reference with independently checked comparator and resources;
independent scoring/native replication and admission criteria; protected target and
submission-policy authority; and four-person limits. Passing generated scorer tests
does not discharge those holds. Source provenance and complete canonical hold wording
are recorded in `source-provenance.json`.

The implementation is newly authored from the mathematical contract and source
inspection. It does not vendor organizer code, data, media or pretrained weights.
Source attribution is retained; organizer repository metadata declares CC0. Source
code rights do not settle movie/media, feature, model or packet redistribution rights.
