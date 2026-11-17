# ZAPBench scientific source contract

Status: source-derived complete forecast geometry and finite-domain scoring adapter. **Zero added qualified benchmarks, authentic runs, fitted references, or evidence of model performance.** This is one zebrafish recording endpoint, not nine conditions, two contexts, 1,557 windows, or 71,721 benchmarks. No cross-animal generalization is established.

## Immutable evidence and method scope

The upstream commit is `7347b3b21a3f332e281b774c945f1505dd966abf`; its actual root tree is `853ce011e5187e084c7e34f90d128599ffd4ab0e`. The predecessor selection incorrectly called the commit a tree SHA. The first acquisition script correctly authenticated all six requested bodies (43,836 bytes) but failed its commit/tree equality assertion. Those bodies were retained and reused, not fetched again. The retained exact commit and tree responses resolve the error. `SOURCE_LOCK.json` pins all 18 ZAPBench source bodies and one separately pinned metric dependency, including bytes, SHA-256, Git blob SHA-1 and immutable links. Code bodies and raw HTTP responses remain only in the matching external engineering-evidence namespace; they are not part of the public source selection.

ZAPBench depends on unversioned `connectomics`, `clu`, `jax`, and other packages in [pyproject.toml](https://github.com/google-research/zapbench/blob/7347b3b21a3f332e281b774c945f1505dd966abf/pyproject.toml). The inspected Connectomics metric file is pinned at `705c0dbdb179ae8001dc7fd88551b86bc7e60c9a`. This establishes the inspected formula, **not the exact dependency used for published runs**. No upstream package, notebook, TensorStore, model, or scientific native dependency was executed.

## Cohort, time, and coordinate contract

[constants.py](https://github.com/google-research/zapbench/blob/7347b3b21a3f332e281b774c945f1505dd966abf/zapbench/constants.py) specifies trace series `240930_traces`, dimensions `(7879,71721)` with axes time/neuron, all neuron columns `0..71720`, stimulus features `(7879,26)`, condition padding one frame at each end, context at most 256 frames, and evaluation horizon exactly 32. Constants are source declarations; no actual object shape, dtype, compression, rights or object generation was admitted.

[The split utility](https://github.com/google-research/zapbench/blob/7347b3b21a3f332e281b774c945f1505dd966abf/zapbench/data_utils.py#L128) first pads each condition to `[a,b)`. For length `L=b-a`, it calculates `test=int(.2*L)`, `val=int(.1*L)`, and `train=L-test-val`. Ordinary target intervals are `[a,a+train)`, `[a+train,a+train+val)`, and `[a+train+val,b)`. Training context consumes the first `C` train frames. Validation and test context begins `C` frames before its target interval. Taxis (condition 3) is absent from training/validation and has holdout target interval `[a+256,b)`, irrespective of context length. For every target start `t`, causal input is `[t-C,t)`, output `[t,t+32)`, stride one. The last start is the target-interval end minus 32. No crossing of padded condition boundaries is valid.

The following inclusive target-start ranges and counts use context 256, sequential source, output offset zero, and training output length 32:

| Condition | Padded interval | Train start/count | Validation start/count | Evaluation start/count |
|---|---|---|---|---|
| 0 gain | [1,648) | 257–423 /167 | 455–487 /33 | 519–616 /98 |
| 1 dots | [650,2421) | 906–1858 /953 | 1890–2035 /146 | 2067–2389 /323 |
| 2 flash | [2423,3077) | 2679–2850 /172 | 2882–2915 /34 | 2947–3045 /99 |
| 3 taxis | [3079,3734) | excluded | excluded | 3335–3702 /368 |
| 4 turning | [3736,5046) | 3992–4621 /630 | 4653–4752 /100 | 4784–5014 /231 |
| 5 position | [5048,5637) | 5304–5430 /127 | 5462–5488 /27 | 5520–5605 /86 |
| 6 open loop | [5639,6622) | 5895–6296 /402 | 6328–6394 /67 | 6426–6590 /165 |
| 7 rotation | [6624,7278) | 6880–7051 /172 | 7083–7116 /34 | 7148–7246 /99 |
| 8 dark | [7280,7878) | 7536–7668 /133 | 7700–7727 /28 | 7759–7846 /88 |

Totals: 2,756 train and 469 validation geometric windows under the stated training setting; 1,189 ordinary test plus 368 taxis holdout windows. Evaluation target coordinates are unchanged for any admitted context 1 through 256. Complete evaluation contains **3,573,427,104 coordinates** (`1557*32*71721`). A single complete float32 prediction tensor set is **14,293,708,416 bytes** uncompressed; targets of the same shape double that amount. This is an arithmetic extent, not measured stored bytes or an acquisition budget.

[common.py](https://github.com/google-research/zapbench/blob/7347b3b21a3f332e281b774c945f1505dd966abf/zapbench/ts_forecasting/configs/common.py#L55) fixes inference ordering `0,1,2,4,5,6,7,8,3`. [data_source.py](https://github.com/google-research/zapbench/blob/7347b3b21a3f332e281b774c945f1505dd966abf/zapbench/ts_forecasting/data_source.py#L105) establishes source/input/output offsets and no implicit neuron masking. [Inference](https://github.com/google-research/zapbench/blob/7347b3b21a3f332e281b774c945f1505dd966abf/zapbench/ts_forecasting/infer.py#L315) iterates all windows and saves `(window, horizon, neuron)` float32 predictions and targets. Sequential substeps feed predictions back within each 32-step forecast; distribution modes are used. The adapter binds completed 32-step predictions and does not implement model generation. Nonzero offset, warmup, neuron subsets, nonsequential sources and other preprocessing are outside this frozen adapter contract.

Official training supports other output lengths dividing 32. Its [loader](https://github.com/google-research/zapbench/blob/7347b3b21a3f332e281b774c945f1505dd966abf/zapbench/ts_forecasting/input_pipeline.py#L108) drops remainder batches and shards; 469 is geometric validation coverage, not a claim that all windows enter every validation pass. The common config uses train-only fitting, validation loss early stopping, patience 20/min_delta .0001, and an unseeded random seed unless a nonnegative seed is supplied. These defaults do not authenticate any published model configuration or reference result.

## Metrics, weights, masks and nonfinite discrepancy

For condition `c`, window `w`, horizon `h` (1 through 32) and neuron `n`, let `d=y-p`. On finite arrays:

- `MAE[c,h] = sum(w,n, abs(d)) / (W[c]*71721)`.
- `MSE[c,h] = sum(w,n, d*d) / (W[c]*71721)`.
- Within-condition scalar MAE/MSE uniformly average the 32 horizon values. Neurons and windows have equal weight within a condition. Overlapping target occurrences are each scored; de-duplicating target times would change the endpoint.
- The official [plot helper](https://github.com/google-research/zapbench/blob/7347b3b21a3f332e281b774c945f1505dd966abf/zapbench/plot_utils.py#L389) takes an arithmetic mean over supplied condition rows for each method/context/horizon/run. Thus conditions have equal weight, not weights proportional to `W[c]`. Which condition rows a paper figure supplies is not established by this helper alone. The adapter reports all nine condition vectors, with an explicitly named all-nine macro; it does not manufacture the paper's exact scalar ranking. No seed pooling is performed.
- There is no target-variance denominator, constant-neuron exclusion, per-neuron normalization, amplitude clipping, variance weighting, or task-specific valid mask in these metric definitions. A constant zero target is well defined. The source's `(-.25,1.5)` values configure categorical bins, not a universal metric clipping range.

The official [metrics tutorial](https://github.com/google-research/zapbench/blob/7347b3b21a3f332e281b774c945f1505dd966abf/colabs/metrics.ipynb) applies `jnp.nan_to_num` separately to targets and predictions before differencing, then averages axes `(0,2)`. Its wording presents custom/recomputed metrics. Conversely the inspected live [Connectomics functions](https://github.com/google-research/connectomics/blob/705c0dbdb179ae8001dc7fd88551b86bc7e60c9a/connectomics/jax/metrics.py#L161) directly subtract arrays with no repair. `PerStepAverage` explicitly refuses masks and merges by sum/count. ZAPBench [heads](https://github.com/google-research/zapbench/blob/7347b3b21a3f332e281b774c945f1505dd966abf/zapbench/ts_forecasting/heads.py#L120) and [metric dispatch](https://github.com/google-research/zapbench/blob/7347b3b21a3f332e281b774c945f1505dd966abf/zapbench/ts_forecasting/util.py#L230) use those dependency functions.

**Consequent scope:** the adapter rejects NaN, infinity, arithmetic overflow and nonnumeric values in either operand. This is an explicit stronger admission rule, not the official nonfinite policy. It implements the common finite mathematical formula using Python double precision with compensated accumulation; no bitwise float32/JAX equivalence is claimed. A later authentic data audit must establish finiteness or select and justify a different, separately named policy. Never silently drop cells or use denominator changes to obtain a convenient score.

## Leakage and input exposure

Training, normalization, learned feature extraction and model selection must not consume ordinary-test targets or taxis responses. Validation can select hyperparameters/early stopping, with the resulting exposure recorded. Causal context is an explicit exception: validation/test input may include preceding split observations, and later windows may include earlier held-out observations. Rejecting all context crossing a target-split boundary is scientifically wrong for the official rolling forecast. No future neural target within a forecast may be supplied as input. Geometric metadata alone cannot prove that a candidate obeyed this rule.

All 71,721 ordered neuron columns are required. Metadata uses the unpermuted trace axis; soma subsets and Rastermap ordering need explicit mapping before comparison. The adapter checks declared contiguous axis coverage, but cannot prove that values actually came from those neurons. Authentic target identity, immutable data generations, candidate isolation, and transport must be supplied by a later protected runner.

The official [stimulus configuration](https://github.com/google-research/zapbench/blob/7347b3b21a3f332e281b774c945f1505dd966abf/zapbench/ts_forecasting/configs/stimulus.py) passes future `240930_stimulus_evoked_response` values through [ReturnCovariates](https://github.com/google-research/zapbench/blob/7347b3b21a3f332e281b774c945f1505dd966abf/zapbench/models/naive.py#L50). Neither this source nor the inspected raw-stimuli notebook establishes how that response array was produced or whether test/taxis responses were used. **Do not admit it as a participant input or leakage-free reference.** The 26 stimulus features and position embeddings also require producer/provenance review before candidate admission. Parameter-free status does not imply absence of target-derived information. The official mean baseline averages each neuron's current context, not the whole recording; its actual saved-run config still needs authentication.

## Implementation, checks and remaining gap

`expected_manifest` derives the full cohort/time/shape declaration; `validate_manifest` requires exact typed equality and rejects extra, omitted, reordered or narrowed endpoints. `validate_window` enforces causal geometry and correct condition membership. `score_complete` streams at most 4,096 neuron values per tile in exact condition/window/horizon/neuron order and yields no score on any omission, extra tile, duplicate, nonfinite value or invalid coordinate. Targets are a trusted caller operand. This library is neither a secure process boundary nor a data transport.

Twelve unittest methods cover the independently derived complete metadata, legal split-crossing context, forbidden taxis training, all boundary failures, strict integers, neuron shape/count, missing/reordered/extra endpoints, nonfinite/malformed/overflow inputs, known MAE/MSE arithmetic, compensated summation, complete-stream prefix failure, and tile identity. The complete reducer control uses an explicitly injected **invented nine-condition, two-neuron, two-horizon plan** with unequal window counts and hand-calculated outputs; production geometry is not weakened. It establishes reduction/control-flow behavior only. It is not a full 3.57-billion-coordinate computation, independent execution of upstream JAX, or authentic numerical parity.

Remaining admission gaps: immutable array/chunk inventory and rights; producer and holdout exposure; actual finite-value census; protected target/input partition and candidate transport; published dependency/config/run identities; competent complete official references; measured full-operation costs; independent complete authentic review. The next bounded operation is specified in `NEXT_OPERATION.json`; it acquires only exact public metadata bodies and does not read any neural array/chunk, fit, or model.
