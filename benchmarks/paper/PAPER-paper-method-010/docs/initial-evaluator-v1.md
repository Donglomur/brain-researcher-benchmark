# Initial Rastermap evaluator: prospective construction component

This additive implementation supplies an executable, source-grounded artifact
evaluator for `PAPER-paper-method-010`. The canonical contract remains pinned at
SHA256 `8764f79a3610f0323b82f342d2bfde9a98b5551241604d44af8684c1a97932bd`.
It has no recorded numerical acceptance target. These policies make proposed
endpoints concrete and testable; they do not amend the canonical contract or
claim that the benchmark is scientifically qualified.

The implementation is
[`evaluator.py`](../implementations/initial-evaluator-v1/evaluator.py).
Dependencies are Python 3.10+ and NumPy. No source data, fitted embedding, native
model, third-party code, or generated result is distributed in this package.
The exact inspected source hashes and semantic mappings are in
[`provenance.json`](../implementations/initial-evaluator-v1/provenance.json).

## Source interpretation and unresolved alternatives

The [paper](https://www.nature.com/articles/s41593-024-01783-4) and the
[pinned source](https://github.com/MouseLand/rastermap/tree/b37644ea52c4cd81f143a9c2cec90286ffd61c49)
ground neural neighborhood preservation, behavior-linked neural structure, and
sorting consistency. They do not define this task's held-out empirical grader.
The source `paper/metrics.py:embedding_quality` counts shared nonself nearest
neighbors and also reports global pair-distance Spearman correlation. Its
default selects at most 2,000 neurons with seed 101 before making both distance
graphs. This package's primary endpoint uses the same shared-neighbor fraction,
but deliberately scores every neuron on withheld time samples. It does not
claim numerical parity with the source's sampled/global metric combination.
The simulation triplet and module-contamination metrics require known latent
ground truth and are not substituted for empirical mouse/hippocampal endpoints.

The paper and notebooks must remain distinct profiles:

| Aspect | Primary source observation | This prospective component |
| --- | --- | --- |
| Hippocampal preprocessing | Notebook z-scores each neuron over all time | Training-only mean/std, `ddof=0` |
| Hippocampal lag/window | Paper lag 0; pinned notebook lag 15 | No native fit; artifact must declare temporal support |
| Position tuning | Paper 30 positions per direction; notebook `n_pos=15` | Linear signed-position-to-superneuron endpoint; no position-bin reproduction claim |
| Mouse grouping | Paper superneurons of 50; notebook bins 200 | Groups of 50, with final remainder retained |
| Hippocampal grouping | Small-neuron source sorting bypasses clustering/upsampling | Groups of 5 for a prospective compression-dependent position endpoint |
| Behavior model | Pinned mouse notebook predicts 128 neural PCs with `neuropop.PredictionNetwork`, delay -1 | Ridge predicts sorted superneuron activity from aligned behavior |
| Behavior metric | Notebook uses uncentered `1-SSE/sum(target²)` | Centered test `1-SSE/sum((target-test_mean)²)`; explicitly different |
| Native fit isolation | Source normalization/mean-time operations precede `itrain`; subsequent temporal operations use full-time projections | A training-only matrix or independently verified adapter is required; `itrain` alone is insufficient |
| Native output | Upsampling quantizes coordinates; native `igood` may exclude zero-variance cells with NaN output | Ties accepted, tau-b handles them; missing/NaN neuron embeddings fail pending explicit population reconciliation |

The grouping sizes are explicit prospective choices: 50 connects to the paper's
mouse figure, while 5 makes compression on the small hippocampal population
depend on the ordering. Neither is a frozen acceptance threshold. Native
preprocessing, binning, position tuning, and behavioral-network reproduction
remain open work. The evaluator never fills source-excluded neurons with
fabricated coordinates or permits a hippocampal-only task pass.

## Frozen prospective scoring policy

For each recording, let `T` be the number of neural time samples, `a=floor(.6T)`,
`b=floor(.8T)`, and `g` the operator-declared purge in samples. Train is
`[0,a-g)`, validation `[a+g,b-g)`, test `[b+g,T)`. Every other time sample is
reported as embargo. Each scored interval needs at least three samples. `g`
must cover the maximum declared temporal fitting support. Validation may choose
development settings, but final fitting remains training-only. A future native
admission must verify this declaration against actual isolated execution.

Every neuron is retained. Mean and scale are learned from training time only;
training-constant neurons use scale 1 and their count is reported. The primary
endpoint is exact nonself k-neighbor retention at `k=10`: for each neuron,
intersect its nearest neighbors in train-standardized held-out activity space
with its neighbors in the submitted one-dimensional coordinate; divide the
total intersections by `N*k`. Distances are squared Euclidean. Canonical
lexicographic neuron IDs resolve ties, and stable sorting excludes self even
when distances tie. No neuron subset or implicit small-recording replacement is
used. The Python API permits other `k` only for explicit engineering controls;
the CLI freezes 10. No threshold, binary reward, or pooled recording score is
defined.

The second endpoint predicts superneuron activity from behavior. Orientation is
canonicalized using the first distinct coordinate pair in neuron-ID order,
making reversal and remainder-group treatment consistent. Contiguous sorted
groups average the normalized neuron activity, including the final short group.
Behavior input centering/scaling, target intercept and ridge weights (`alpha=1`)
are fit only on training samples. The output reports per-group centered test
R², its unweighted macro mean over defined groups, group sizes, and the number
of constant test groups with undefined/null R². Different-size groups receive
equal macro weight; the per-group vector permits inspection. Constant targets
are never silently awarded zero or perfect performance.

Each embedding also requires a repeat-seed artifact and either a neuron
subsample or missing-training-time artifact. Absolute Kendall tau-b measures
order stability on shared neurons, with pairwise ties removed from the
appropriate denominator. Complete reversal is equivalent; all-tied output is
undefined/null. Paired methods must declare the same perturbation seeds,
neuron supports, and fitting-time digests. Repeat-seed and missing-time controls
retain every source neuron; a neuron-subsample control must retain a strict
subset of at least three known neurons. These are robustness measurements,
not biological replicates, uncertainty intervals, or independent sessions.

Methods are compared per recording by candidate-minus-baseline neighborhood
retention and behavior macro R². There is no post-hoc selection of a favorable
recording or aggregation across species. The evaluator requires matching
declared input hashes, access condition and tuning-budget count. Those checks
establish receipt consistency, not actual access isolation, compute equivalence,
baseline competence or authenticity of training claims.

## Native source input bridge

`load_source_npz(path, role, expected_sha256)` checks the acquired file's SHA256
against the operator's exact pin, then uses `np.load(..., allow_pickle=False)`.
The pin is an acquisition receipt; the caller must separately resolve it to the
approved OSF asset/version. The function downloads nothing.

* `hippocampus`: `spks` is neurons × time; `loc_signed` has one value per time
  sample and may contain source-valid NaNs. The neural sample interval is 0.2 s.
  The bridge uses `loc_signed` as the single position feature. `loc2d`,
  `pyr_cells` and published tuning maps are not used for this prospective
  endpoint and remain part of native claim reconciliation.
* `mouse`: `spks` is neurons × time; `tneural` and `run` share its time axis;
  `beh` is camera samples × features with strictly increasing `tcam`.
  The bridge linearly interpolates each camera feature within each frozen
  train/validation/test interval, appends running speed, and never extrapolates
  or uses camera observations across those intervals. Missing endpoints yield
  NaNs. This is an explicit prospective clock-alignment rule, not a claim to
  reproduce `neuropop`'s native delay/interpolation semantics.

Any behavior row containing NaN is excluded from regression with separate
included/excluded counts for each split. Neural geometry still uses every
neuron and all test neural samples; missing position does not silently shrink
the neural endpoint. Infinity or nonfinite neural activity fails closed. The
public source adapter assigns stable IDs `row:000000`, `row:000001`, etc. Actual
empirical membership, processed schema and recording identity require native
qualification; counts alone cannot prove biological completeness.

## Artifact and CLI interface

From the implementation directory:

```sh
python3 evaluator.py /absolute/operator/request.json --output /absolute/operator/report.json
```

The operator JSON has `purge_samples`, `maximum_fit_lag`, and `recordings` with
exactly one entry for each role `hippocampus` and `mouse`. Each entry has
`role`, `source_npz` (local path), `expected_sha256` (64 lowercase hex digits),
and `embedding_artifacts` (local JSON paths). Both populations are mandatory:
137 hippocampal and 34,086 mouse neurons. An explicit API-only engineering flag
allows generated small arrays and labels every output accordingly; the CLI has
no population bypass.

Every embedding JSON contains:

| Field | Meaning |
| --- | --- |
| `name`, `role` | Unique method name; exactly one `candidate`, other methods `baseline` |
| `neuron_ids`, `embedding` | Every original neuron exactly once; one finite scalar coordinate each; ties allowed |
| `input_sha256` | The exact input file receipt |
| `train_index_sha256` | SHA256 of ascending train indices encoded as little-endian signed int64 bytes (`index_sha256`) |
| `access_condition` | `paper_and_data` or `paper_data_official_code`, matched across methods |
| `official_code_revision` | Required in the code condition: `b37644ea52c4cd81f143a9c2cec90286ffd61c49` |
| `seed` | Nonnegative declared fit seed |
| `maximum_fit_lag` | Matched to the frozen protocol; must fit inside the purge |
| `tuning_budget` | Positive allowed development-configuration count, equal across compared methods; realized usage is unverified |
| `perturbations` | At least one repeat seed plus one neuron/time robustness artifact |

Each perturbation has `kind` (`repeat_seed`, `neuron_subsample`, or
`missing_time`), `neuron_ids`, `embedding`, `seed`, `fit_time_indices`, and the
same provenance fields as its parent. Its `train_index_sha256` hashes its own
explicit fitting indices. Every fitting index must be a unique member of the
base training interval; missing-time controls must remove some of them, other
controls must use the complete base training indices in their original order.
Repeat seeds must differ from the base seed. All perturbations stay tied to the
original input hash, access condition and approved source revision.

The report includes exact input, fitting-index and CLI embedding-file hashes,
split/embargo counts, population counts, endpoint vectors and comparisons,
constant-neuron/target counts, behavior exclusions and all unresolved holds.
No candidate program is imported or executed. Operator reference artifacts and
test arrays must remain inaccessible to candidates; JSON declarations alone
cannot demonstrate protected evaluation or replay isolation.

## Controls, resource bounds and remaining gates

Run all committed generated controls with:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p '*.py' -v
```

Independent reference controls derive exact neighbor identities from
`[0,1,4,10]`: identical/reversed geometry preserves all k=1 and k=2 neighbors;
the permutation `[0,4,1,10]` preserves 0 at k=1 and 1 at k=2. The reference
worker also checked these results against the unchanged pinned source metric
functions and obtained global pair-distance Spearman `5/7` for that permutation.
Other controls test train-only normalization, exact purge accounting,
source-valid NaN behavior handling, centered-versus-uncentered metric
differences, null constant targets, tied order stability, full-ID permutation,
reversal with remainder groups, large scalar translation, paired provenance,
test-time rejection, safe NPZ loading and rejection of incomplete CLI scope.

These controls use bounded generated arrays and establish implementation
behavior only. No empirical payload, native Rastermap fit, scientific campaign,
model/API execution, dependency installation or archive download was performed.
The package retains all scientific, protected-reference, full-population and
rights gates. Both source identities, empirical replay and competent equal-budget
baselines are still needed before native admission; neither a passing scorer
test nor attractive raster is evidence of scientific qualification.

Exact neighborhood scoring allocates at most `row_block × N` distances plus
the full input/normalized matrices and `N × k` neighbor indices. Default
`row_block=64` avoids a full `N × N` matrix, but runtime still grows quadratically
in neuron count and linearly in held-out feature count for neural distances;
row sorting adds `O(N² log N)` work. The NPZ bridge materializes the processed
arrays. Full mouse memory/runtime has not been measured, and the author's
16–32 GB guidance is not a local measurement. No approximation or neuron
subsampling is silently enabled to make it fit. Empirical resource qualification
remains required.
