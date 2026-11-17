# Full retinal held-out comparison

`score.py` compares author and candidate predictions for the registered cell
`20161028_1` on identical held-out rows and all 147 recording sites. It joins rows
and sites by identity before calling the unchanged, SHA-256-pinned
`registered-runtime/programme/scientific/retina_model.py::metrics` function.
The original arithmetic mean of masked per-site Pearson correlations is retained.
No simulator, fitting, source download, or split generation is performed.

This supplies the missing standalone paired prediction comparison. It does not
authenticate a historical cache or split, admit an author baseline, estimate
uncertainty, select a minimum effect, or declare paper improvement. A report can
be computed from internally consistent but historically incorrect inputs; only
external operator source qualification can establish historical equivalence.
The rounded published 0.25 is never used as a reproduced comparator. The
preserved broader 36-family programme remains separate and unchanged.

## Operator use

Use a Python environment with NumPy already available. The generated controls
record the tested interpreter and NumPy version in the external handoff.

```sh
python3 -I -B score.py \
  --targets /operator-private/targets.json \
  --author /operator-private/author.json \
  --candidate /operator-private/candidate.json \
  --output /operator-private/new-comparison.json
```

Run from this directory or pass the script's absolute path. The CLI refuses to
overwrite an existing report. Keep targets, predictions and reports outside Git.
Only the operator should execute this comparison. The module does not create a
participant sandbox or prove that a candidate was frozen before test exposure;
participant transport and independent custody remain required. The API is
`compare(operator, author, candidate)` for an admitted evaluator to call later.

The target JSON has exactly these keys:

| Key | Required content |
| --- | --- |
| `schema` | `jaxley-retinal-target-v1` |
| `cell_id` | `20161028_1` |
| `sites` | All 147 site objects in the target matrix column order |
| `splits` | `train`, `val`, `test` lists, each nonempty, disjoint, jointly containing every integer row 0–15359 once |
| `labels` | Held-out calcium matrix, rows in `splits.test` order, 147 columns |
| `mask` | Numeric 0/1 matrix with the same shape |

Each site has exactly `field` (1–15), `branch` (nonnegative integer), `bin` (0–3),
and `raw_roi_ids` (nonempty positive integer list). The `(field, branch, bin)`
keys must be unique. Exactly 232 unique `(field, raw_roi_id)` pairs must map once
to those sites; all 15 fields must occur. These coordinates follow the preserved
author-derived preprocessing: rows 0–1023 belong to field 1, rows 1024–2047 to
field 2, and so on. Each site is observed on rows from its field, so the supplied
mask must exactly equal this field support. This is a specific source profile;
a differently processed cache needs explicit scientific reconciliation.

Copy the actual published split indices into `splits`; the scorer does not
reconstruct them from a default seed, assert that 128 test rows were published,
or accept a reduced seven-field panel. Those historical indices remain
unrecovered in the registration. Labels may be `null` only where the mask is
zero. No normalization, delay correction, site merging or filtering occurs here.

Each prediction JSON has exactly `schema` (`jaxley-retinal-prediction-v1`),
`cell_id`, `test_row_ids`, `site_keys`, and `predictions`. `site_keys` is a list of
`[field, branch, bin]` triples. Rows and columns may have any order provided all
and only the target identities appear exactly once. Both author and candidate
use this schema. Predictions must be finite real numeric values for every row
and site; neither packet can supply a mask. Boolean, string, nonfinite and lossy
integer values are refused. Target and prediction units are the source's
preprocessed calcium response units, with the same source normalization and
label delay already applied upstream.

## Output and boundaries

The result includes author and candidate means, their paired difference,
all site correlations and support counts, and canonical SHA-256 digests of the
inputs and identity mapping. It never pools observations across sites or weights
site correlations by their valid counts. Constant or insufficiently observed
sites remain in the report and make the affected all-site mean undefined. No
site is dropped to recover a number. Arithmetic overflow/nonfinite computed
metrics are refused. Source kernel hashes are checked before use.

`paper_win` and `uncertainty` remain null. Sites and stimulus rows are dependent
observations from one cell; a sitewise standard error would not establish
biological replication. A complete comparison still requires authenticated
232-to-147 correspondence, exact historical split/cache/checkpoint, admitted
author replay, protected candidate freeze, a meaningful effect, dependence-aware
uncertainty, budgets, and explicit retinal versus whole-programme scope.

## Evidence and generated controls

The implementation is based on the existing task and its source-grounded
improvement contract, the preserved metric/preprocessing kernels, and the
focused repository audit identifying missing participant grading. It does not
claim new source retrieval or authentic data preparation. `SOURCE.json` records
the source URLs, revisions and local source pins.

`test_score.py` uses invented 147-site/232-ROI metadata and synthetic numerical
values. It exercises the actual comparison and CLI, independent exact +1/-1
correlation expectations, unequal observation counts, arbitrary identity order,
masked-value exclusion, undefined sites, missing/duplicate identities, split
overlap, altered masks, malformed values, source pin changes and report overwrite
refusal. Run it through the reviewed shared test pool under the wave's resource
rules. These are software controls, not author reproduction or paper performance.
