# Original AJILE random-forest endpoint component

This component adds the original downstream **rest/movement decoding accuracy** path missing from the earlier reconstruction evaluator. It fits the source's three fixed random forests to prepared training signals, evaluates already frozen imputer outputs, and retains all 36 participant-by-dropout curves from the complete 180-case panel. It requires fully observed, mean-imputed, author DDPM, deterministic neural imputer and candidate arms. It neither fits an imputer nor supplies missing author outputs.

The original task, improvement contract and `initial-evaluator-v1` remain unchanged. This endpoint supports two distinct future outcomes: source-paper reproduction and same-task improvement. The author-DDPM curve and candidate-minus-author differences remain separately reported; no automatic success threshold merges them. Generated controls establish software behavior only. Original event/day provenance, trained comparators, actual full-panel decoder execution, the numeric published result vector, and meaningful paired participant-level improvement remain unqualified. Neither outcome nor current SOTA is claimed. Matched paper-plus-data and paper-plus-data-plus-author-code participant conditions require a separate qualified delivery/execution layer.

## Source fidelity

The pinned [author experiment](https://github.com/mackelab/neural_timeseries_diffusion/blob/7e9c3314dc242c36a206d18f13158c049e84cd1d/ntd/ajile_imputation_experiment.py) uses float32 standardized event × channel × time signals, merges observed channels with imputed hidden channels, reverses training normalization, and flattens channel-major/time-minor. It does **not** compute band-power features or apply the dataset's quality mask during decoding. The component follows this behavior and includes every supplied test event in the accuracy denominator.

Each RF uses 240 trees, maximum depth 9, balanced class weights, out-of-bag scoring and seed equal to fold index 0, 1 or 2. `n_jobs=1` only makes the source default single-process resource behavior explicit. The channel mask and RF row permutation use independent `default_rng(repeat)` instances with the same repeat seed 0–4. The observed count uses NumPy rounding of `(1 − dropout) × channels`; dropout is .5, .7 or .9. For training length N, each fold excludes `floor(N/3)` permuted rows and sorts retained indices with `setdiff1d`; remainder rows remain in **all** three fits. Replacing this with `array_split`, stratified folds or shuffled retained rows would change the source experiment.

The [source loader](https://github.com/mackelab/neural_timeseries_diffusion/blob/7e9c3314dc242c36a206d18f13158c049e84cd1d/ntd/datasets.py) concatenates earlier event days in sorted order before training and holds out the latest available day. `source_day_indices` implements that order, and scoring requires prepared row IDs to match it exactly. This differs from simply retaining the original order when days interleave. The latest-day source rule is recorded as such; it does not establish the paper's first-six-days/day-seven mapping. No alternative split is introduced.

**Figure error-bar correction:** the [author plotting notebook](https://github.com/mackelab/neural_timeseries_diffusion/blob/7e9c3314dc242c36a206d18f13158c049e84cd1d/notebooks/ajile_plots.ipynb) averages the three RF accuracies within each replicate, then averages five replicates. Its error bar is `np.std(imputation_accuracy − mean_imputation_accuracy)` over those five paired replicates, with `ddof=0`. It is not the marginal SD of imputation accuracy. The output retains both quantities under separate names; `source_figure_errorbar_paired_gain_sd` matches the plotted calculation. The current canonical improvement contract's aggregation description needs this correction through integration. Five masks/folds are dependent repetitions, not independent participants.

## Operator interface

Use an existing environment with NumPy and scikit-learn. PyTorch is needed only by the generated numerical parity test. No installer, downloader or model API is invoked. A native `score-case` call fits RF models and therefore requires the separate frozen native execution protocol and shared lease; construction authorization alone does not authorize a real run.

`score-case` takes an **operator-only NPZ**, never a candidate-facing packet:

| Field | Meaning |
|---|---|
| `train_z`, `test_z` | Source-standardized events × ECoG channels × time, before source float32 conversion. Authentic geometry is the original participant channel count and 1001 samples. |
| `train_mean`, `train_scale` | One-dimensional per-channel training-only normalization, expressed in retained source units. These are not fitted by this component. |
| `train_labels`, `test_labels` | One binary rest/movement label per corresponding event; original label codes 1/2 must already have been mapped to 0/1. |
| `train_row_ids`, `test_row_ids` | Unique strings in source loader order, with no overlap. |
| `native_days`, `native_row_ids` | Complete native event roster in original file order. Preparation must preserve every row, split by source days and bind normalized arrays/labels to these IDs. |
| `source_sha256` | Scalar string identifying the original native source file. A declared hash alone does not prove authenticity. |
| `author_ddpm`, `deterministic_nn`, `candidate` | Frozen standardized imputation tensors matching `test_z`, each generated with this case's mask. The evaluator overwrites observed-channel predictions with the actual observations. |

All five arms share one fitted RF per fold. Missing arms, nonfinite values, changed source geometry, nonbinary labels, day/row mismatches and overlapping row IDs fail. The previous reconstruction converter omits movement labels and its candidate inputs apply observed quality masking; those exports are **not** directly eligible inputs to this source endpoint. This addition does not silently adapt their meaning.

```sh
python endpoint.py score-case /operator/prepared-case.npz /operator/case-score.json \
  --participant EC01 --dropout 0.5 --repeat 0 --kind authentic_input
python endpoint.py aggregate /operator/all-case-receipts.json /operator/panel-score.json
```

The aggregate input is a JSON list of 180 `{ "path": "relative-case-score.json", "sha256": "..." }` records. The aggregator requires EC01–EC12 × all three dropout levels × repeats 0–4, each containing exactly three folds and all five arms. It checks participant event/normalization-input lineage metadata, paired training-row identities, source mask choices, matching fully observed controls across dropouts, integer counts, and denominators. It reports per-replicate and mean accuracy for each participant/dropout, original paired-gain SD, diagnostic marginal SD and paired candidate-minus-DDPM replicates. It introduces no grand scalar, threshold or inference claim.

The content digest binds each input file, and receipts retain source/event-order hashes and actual NumPy/scikit-learn versions. Receipts are trusted operator outputs, not cryptographically authenticated external claims. Prepared arrays, labels, imputer predictions and event identities must remain outside public Git and outside candidate access. Independent process/state isolation between masks remains necessary; this scorer does not implement the candidate executor. Calibration to the original source environment is still needed even if generated-array results agree in the available environment.

## Validation and limits

`tests/test_endpoint.py` checks source day ordering, nondivisible training folds, inverse normalization/flattening, observed-channel invariance, complete-panel aggregation and meaningful malformed inputs. It also executes the unchanged pinned author function on generated arrays, using an array-returning sampling stub and the real RF classifier, and compares its three reported accuracies to this component. No diffusion network is constructed or run. The vendored MIT source and license support this independent numerical oracle; source byte pins and the cached notebook projection's scope are recorded in `provenance.json`.

All six generated controls passed through the shared reviewed two-slot pool (attempt `paper01-add005-rf-v1-03`); the test runner reported 4.669 seconds, with 2.320 child CPU seconds and 260,784,128-byte peak child RSS recorded by the pool. Two preceding attempts encountered busy slots and launched nothing. The numerical oracle covers one generated participant/mask and three actual RF fits per implementation; the 180-case aggregation control uses generated count receipts, not 180 authentic decoder runs. Actual test command, resource receipt and frozen file hashes are recorded in the external handoff. No authentic observations, targets, labels or predictions were opened for construction, and no native model/data work was performed. Full-panel authentic preparation, preserved labels, paper-day reconciliation, source-specific data rights, author/deterministic training provenance, secondary correlation/spectral checks and calibrated controlled scientific comparison remain required.
