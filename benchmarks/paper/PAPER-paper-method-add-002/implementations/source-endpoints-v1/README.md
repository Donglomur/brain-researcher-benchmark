# Original source endpoint components

This package implements the original Fig.2 trial-wise trajectory R² and the
blocked-reconstruction root-error calculation for `PAPER-paper-method-add-002`.
It addresses the lack of a public same-task scoring component. It does not make
the combined benchmark ready or establish a paper improvement.

The same source-faithful metrics support two separate first-class outcomes:
reproducing the original findings and exceeding them on the original task.
Neither outcome has been demonstrated here. Future paper+data and
paper+data+author-code conditions require independently authored, paired outputs
and separate scores; this operator component does not implement that delivery
or authoring isolation. The task is not counted twice for these outcomes.

The executable code is new and does not vendor the analysis repository. Exact
author-source revisions, hashes, locators and roles are in [SOURCE_MAP.json](SOURCE_MAP.json).
The predecessor registration and canonical improvement contract are unchanged.

## Fig.2 behavior

`source_schedule` reconstructs the released `plot_k_fold` seed-0 legacy NumPy
permutation sequence independently for straight and curved reaches. It retains
all 265 straight and 246 curved trials, five folds and twenty repeats. Each
straight fold tests 53 trials; each curved fold tests 49. One curved trial per
repeat remains in **every training fold**, producing 4,900 curved test occurrences
rather than 4,920. The 5,300 straight occurrences and all repeated identities
remain separate. Array row indices are not authenticated biological trial IDs.

The original source slices are neural `[55:-15]` and movement `[65:-5]` in the
150-bin source arrays. These produce 80 aligned bins with a 10-bin lag. The
package does not resolve the source-paper physical-window discrepancy or alter
preprocessing. Neural normalization and decomposition may have seen all trials;
decoder holdout alone does not establish unseen-trial representation learning.

The decoder learns per-bin displacement and integrates it from the true initial
hand position, prepending that starting sample. `integrate_displacements` retains
this convention without multiplying by a time step. The scorer requires the
exact initial position in every predicted trajectory.

R² subtracts each trial's temporal mean **separately for X and Y**, then pools
squared residuals and squared deviations across time and both coordinates. This
differs from pooling X/Y before centering and from averaging two coordinate R²s.
Negative values are retained. The reported main score averages all trial scores
over the original equal-width folds and repeats, separately by condition. The
mean within-fold population SD matches the author function; it is not a standard
error or confidence interval. Zero-denominator trials fail explicitly instead
of being dropped or assigned fabricated finite scores.
Calculations use float64; exact last-bit agreement with a float32 author run is
not asserted. The source formula and accumulation units are retained.

An operator-created NPZ supplies exactly:

| Key | Shape | Meaning |
| --- | --- | --- |
| `movement` | `[150,511,2]` | Full original position targets, operator only |
| `straight_prediction` | `[20,5,80,53,2]` | Position predictions in source fold order |
| `straight_test_indices` | `[20,5,53]` | Original row indices from `source_schedule` |
| `curved_prediction` | `[20,5,80,49,2]` | Position predictions in source fold order |
| `curved_test_indices` | `[20,5,49]` | Original row indices from `source_schedule` |

```sh
python3 -I -B endpoints.py score-fig2 \
  --input /operator/fig2_predictions.npz --recipe source_code_ridge1 \
  --summary /operator/fig2_summary.json --private-details /operator/fig2_details.npz
```

The command checks complete tensor shapes, finite values, source permutation
order and initial-position access. It writes separate straight/curved summaries
and private trial-level scores with fold IDs, training-only identities and actual
per-trial test counts. Keep movement, predictions and detailed outputs outside
Git and outside candidate access. This library is an operator scorer, not a
security boundary or participant transport.

`--recipe` records the operator's declared provenance: released code defaults to
ridge alpha 1 with its appended constant penalized; the paper describes OLS.
`paper_ols0` labels that alternative. The scorer does not fit or authenticate
either recipe. Choosing a flag cannot resolve the discrepancy or qualify a
baseline. The source condition-averaged raw control has a different splitting
route and remains a required separate comparator, alongside the declared raw,
slice-type, CP/TCA and any other source-panel comparators. No roster is silently
admitted by scoring one supplied prediction tensor.

## Reconstruction behavior

`reconstruction_error` accepts target, prediction and a binary source training
mask with identical `[trial,neuron,time]` layouts. One means observed/training;
zero means held out. For each trace, the source removes `cut_bins` from the first
and last zero boundaries. For disconnected holes, it does **not** trim each
interior block. The exact slicing convention is retained, including Python's
negative slice starts for oversized cuts. Empty held-out support fails explicitly.

The source quantity is `sqrt(SSE / heldout_entry_count)`. Both RMSE and MSE are
returned with pre/post-trim counts. The zero-filled training MSE uses all tensor
entries as denominator and is separately labelled from training-entry MSE.
No automatic normalized error, mask generation or rank aggregation is added.

```sh
python3 -I -B endpoints.py score-reconstruction \
  --input /operator/reconstruction_cell.npz --cut-bins 5 \
  --summary /operator/reconstruction_cell_summary.json
```

The NPZ keys are exactly `target`, `prediction`, and `training_mask`. The cut of
5 above illustrates the explicit argument; it does not declare a recovered panel
setting. One result is one externally frozen rank/type/mask realization. Every
original mask, cut setting, full rank/seed roster and companion control still
requires source authentication before panel comparison.

## Verification and remaining work

Run `test_endpoints.py` with the shared lightweight test pool. The optional
`--author-source-dir` enables differential execution of only named functions
extracted from the SHA-256-pinned cached author source. It does not import the
author repository or load data/model arrays. Generated controls exercise
coordinate offsets, unequal XY variance, negative R², zero denominators, true
start integration, both full trial schedules, omitted/reordered folds, mask
polarity, disconnected holes, edge trimming, denominator differences and the CLI.

The source-code schedule is recovered; authenticated original biological trial
membership and saved original permutation artifacts are not. Original figure
scores, model predictions, all comparator assets, reconstruction masks/rank
profiles, OLS/ridge and physical-window reconciliation, valid paired uncertainty,
meaningful effect, and a joint decision for decoding and reconstruction remain
unresolved. No authentic arrays or historical private answers were read, no
scientific model was fitted, and no candidate was evaluated in this build.
