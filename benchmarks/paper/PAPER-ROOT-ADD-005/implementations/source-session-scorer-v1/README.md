# Original session encoding score component

This trusted-operator scorer compares a frozen author prediction archive and a
candidate archive on the original **12 ordered session folds**, separately for
each of participants `01`, `02`, and `03`. It computes per-voxel Pearson
correlations inside each fold and their arithmetic mean. It retains the sign,
every trial repetition, and every declared voxel. It reports paired candidate
minus author changes on the same observations.

The predecessor `initial-evaluator-v1` is unchanged. That implementation uses a
different, prospective image-family/category split and nested ridge regression.
Its pooled signed SSE/SST R² and image averaging cannot supply this source score.

This component does not establish an empirical improvement benchmark. Authentic
full-cohort rows, source masks, Figure 2 noise-ceiling conversion, author
predictions, protected execution, inference, resource measurements and an
admitted paper-win rule remain unresolved. Reproducing the original findings and
exceeding them are separate first-class outcomes. Neither has been demonstrated
here. Paired paper+data versus paper+data+author-code delivery conditions still
require protected execution and separately reported results; this scorer does
not establish either delivery condition.

## Source estimator and split

The fixed source revision is
`b1843e7eb92858c9c4a9ef88b4a5faea24752b49` of
[dimension_encoding](https://github.com/ViCCo-Group/dimension_encoding/tree/b1843e7eb92858c9c4a9ef88b4a5faea24752b49).
[run_linregcv.py](https://github.com/ViCCo-Group/dimension_encoding/blob/b1843e7eb92858c9c4a9ef88b4a5faea24752b49/scripts/run_linregcv.py)
joins the 66 image dimensions to single-trial response rows and standardizes
features globally. Its default
[LinRegCVPermutation](https://github.com/ViCCo-Group/dimension_encoding/blob/b1843e7eb92858c9c4a9ef88b4a5faea24752b49/dimension_encoding/glm.py#L1097)
uses intercept OLS, unshuffled 12-fold KFold, per-fold Pearson correlation and an
arithmetic fold mean. This scorer consumes predictions; it neither restricts a
candidate to OLS nor verifies how either archive's predictions were made.

The [paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC11576512/) describes
leave-one-session-out evaluation. The source code implements contiguous row
blocks. `source_folds` therefore requires the operator's original row order to
make those blocks exactly twelve distinct complete sessions. It rejects mixed
sessions, split sessions and incompatible block lengths. It never sorts sessions
to repair the source order. Unequal KFold blocks follow the source rule: earlier
folds get the remainder rows, and all twelve folds still receive equal metric
weight. This compatibility check is not an authentication of supplied metadata.

Neither pooled correlation nor either form of R² is substituted. A test with all
within-session correlations equal to `1` but pooled correlation below `−0.9`
distinguishes these estimators. Negative fold means remain negative. No
across-voxel/participant scalar, noise-ceiling division, significance threshold,
permutation test or Figure 6 variance partition is inferred from this metric.

## Operator inputs

Use Python 3 with an existing NumPy installation. The CLI accepts one JSON roster
and three numeric NPZ archives, always with `allow_pickle=False`:

```sh
python3 scorer.py --roster roster.json --reference observed.npz \
  --author author-heldout.npz --candidate candidate-heldout.npz --output scores.json
```

The roster has `task_id: "PAPER-ROOT-ADD-005"`,
`schema_version: "source-ordered-session-mean-pearson-v1"`, and a `participants`
object with exactly keys `01`, `02`, `03`. Each participant record contains:

| Field | Meaning |
| --- | --- |
| `trial_ids` | Unique exact identifiers in **original source row order** |
| `stimulus_ids` | Trial-aligned image identities; repetitions remain separate |
| `session_ids` | Trial-aligned source session identities, twelve complete sessions |
| `voxel_ids` | Unique voxel identities in the complete original evaluation mask order |

Independent source preparation must authenticate these lists and their masks.
This scorer cannot determine whether a declared image/voxel subset is the
original full cohort merely from internally consistent IDs. It does not invent a
trial total from the paper's number of unique images.

For each participant, the reference NPZ has these exact keys, replacing `01`
with `02` and `03` as appropriate:

| Key | Shape |
| --- | --- |
| `sub_01_trial_id` | `[trials]`, unique strings |
| `sub_01_stimulus_id` | `[trials]`, strings |
| `sub_01_session_id` | `[trials]`, strings |
| `sub_01_voxel_id` | `[voxels]`, unique strings |
| `sub_01_response` | `[trials, voxels]`, finite numeric values |

Each prediction archive instead has `sub_01_trial_id`, `sub_01_voxel_id`,
`sub_01_heldout_session_id` and `sub_01_prediction`. The latter two have shapes
`[trials]` and `[trials, voxels]`. Held-out-session labels must match the source
session for each trial. This verifies declaration consistency; it cannot prove
that a model excluded the corresponding responses from training. Protected
replay and candidate freezing still need an independently enforced operator path.

Each archive may order rows and voxels differently. Exact bijections restore the
roster order before scoring. The scorer rejects missing/unknown/duplicate IDs,
extra archive keys, wrong trial-to-stimulus/session mappings, missing participants
and nonfinite values. No fuzzy filenames, case folding, category merges, voxel
intersections or dropped observations are allowed. All archives must be trusted
operator files: this is not an untrusted upload service.

## Output and numerical limits

Outputs contain each participant's complete ordered voxel IDs, trial/image/voxel
counts, fold boundaries, twelve author and candidate Pearson maps, their means,
paired mean changes and defined-fold counts. A zero-variance observed or
predicted fold produces `null`; any undefined constituent makes that voxel's
mean and paired difference `null`. No `nanmean` changes the fold population.
Pearson calculations scale columns before centering to avoid product overflow
or underflow at extreme finite units. They use the same mathematical estimator,
not the identical floating-point operations as the author.

The CLI retains the same open file descriptors for all four inputs through
hashing and decoding, verifies their hashes and file metadata afterward, and
rejects detected changes before scoring. A pathname replacement cannot make the
decoder read a different file under the original file's hash. It records SHA256
values and exclusively creates its output to preserve existing evidence. These
checks bind the decoded inputs, not source identity or a training protocol. Do not publish response archives, predictions, private
paths or full sensitive scoring outputs in the repository.

This implementation loads numeric archives into memory and uses identity-indexed
copies. Original full-cohort memory/runtime and a streaming native HDF5 export
remain unmeasured. Its generated controls exercise the score path only; they do
not authorize large authentic numerical preparation or model execution.

## Verification

Task-local pytest controls cover estimator distinctions, negative scores, unequal
fold sizes, exact session equivalence, independent row/voxel order, repetitions,
all-three-participant coverage, malformed identities/values, constant columns,
extreme finite scales, input hashes, safe NPZ loading and output preservation.
The coordination test pool must run them under the existing resource policy.
The shared pool ran 21 controls successfully in 0.28 seconds. A separate
generated control extracted only `pearsonr_nd` from the acquired immutable
author source and verified per-column and fold-mean parity, including constant,
shifted and anticorrelated columns (maximum finite difference `2.22e−16`). This
used no authentic arrays or fitting. Exact source and test records are pinned
in `provenance.json` and the external handoff.

Suggested integration is a new source-metric software component linked beside
the preserved prospective evaluator. Keep the canonical task `source_unresolved`
and the historical results unchanged. No scientific readiness promotion is
supported by this change.

## Current Pearson arithmetic repair

The current implementation subtracts a finite anchor before scaling each Pearson
input. This preserves representable variation near a common offset; opposite
finite extremes are halved only when their difference would overflow. Constant
columns remain undefined and all original population, grouping, aggregation and
scientific qualification limits remain unchanged. Historical source/provenance
records retain their original hashes; `CURRENT_SOURCE.json` identifies this
maintained numerical revision.

The new `test_centering_regression.py` controls use generated values and an
independent exact-rational/80-digit Decimal oracle. They do not qualify an
authentic reference, candidate run, reproduction or improvement.

The input-identity regression controls use generated complete three-participant,
twelve-fold archives. They check unchanged scores and hashes, pathname
replacement followed by restoration, and in-place replacement followed by
restoration during decoding. These are software controls, not empirical
reproduction or candidate evaluation.
