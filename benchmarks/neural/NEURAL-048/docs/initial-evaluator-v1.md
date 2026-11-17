# NEURAL-048 initial evaluator

This independently authored, standard-library component builds causal predictor histories and recomputes matched, worm-level direction log-loss contrasts. It provides executable construction source, not an admitted native benchmark. No animal data, trained model, authentic reference result or scientific qualification is included.

The immutable task remains `task.json` (SHA256 `2d8821217a1013fd40be7b1ebc9c7ebf99ad3cc0a7f4112bbf595da34fd44bdd`). Its whole-worm/episode holdout and worm-level log-loss endpoint govern this component. Source and prospective decisions are separated below.

## Source mapping and prospective policy

The [primary paper](https://www.nature.com/articles/s41593-026-02257-5) and [author code at c7e7e18](https://github.com/flavell-lab/SAAV_Decoding/tree/c7e7e18a84cde5dc02df9d63492293b38402eb2c) predict dorsal versus ventral turns after reversals. The loader reads four lab-local aligned CSVs; positive/dorsal supplies label 1, negative/ventral label 0. Channel 0 is SAAV calcium, channel 1 head curvature, and channel 2 is zero. Notebook pairs `[0,1]` and `[2,1]` compare neural-plus-behavior with behavior alone. It crops frames 38:50, excludes events containing NaNs, and uses four-frame windows. Its class-specific shuffled/rotated event folds carry no worm identities. Published balanced accuracy and class-binomial resampling are not this task's log-loss endpoint or biological-unit uncertainty.

The paper aligns signals using complete head-curvature half-cycles and labels direction using post-reversal behavior. These aligned frame numbers cannot certify causal timestamps. Public H5/MAT-to-CSV conversion and per-animal identity retention remain unresolved. Small pinned source files and a previously cached notebook were inspected; no source code is vendored or executed. Exact pins appear in `../implementations/initial-evaluator-v1/provenance.json`.

Prospective component policy is frozen in `evaluator.POLICY`:

- `p` means probability of a dorsal postreversal turn; label 1 is dorsal and 0 ventral. This source-grounded direction component does not settle the broader task's final target/window selection policy.
- Bernoulli loss is `-log(p)` for label 1 and `-log1p(-p)` for label 0, in nats. Finite probabilities must satisfy `0 < p < 1`; endpoints are rejected, with no clipping or source training-loss epsilon.
- Observations are averaged equally within each worm, then worms equally. The primary contrast is behavior loss minus neural-history loss, so positive favors neural history. Multiple windows in one episode remain nested observations; their number must be frozen before prediction, not selected by a submission.
- All three arms—behavior, neural history, and time-shifted neural history—must predict exactly the same full frozen observation set. Secondary contrasts are behavior minus shifted and shifted minus neural. Constant probabilities are scored and diagnosed; chance/null arms are valid engineering controls.
- Paired 95% percentile intervals resample entire worm contrasts. For two to five worms, all ordered size-N bootstrap draws are enumerated. Above five, 10,000 draws use a local seed 1729. Percentiles interpolate linearly at `(draw_count - 1) * q`. One worm receives a descriptive contrast and no interval. These prospective development intervals are not a scientific admission threshold; small samples can be poorly calibrated.

## Interfaces

`evaluator.py` has no third-party dependency. Import it by file path or run:

```sh
python3 benchmarks/neural/NEURAL-048/implementations/initial-evaluator-v1/evaluator.py \
  operator-reference.json matched-predictions.json --output report.json
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s benchmarks/neural/NEURAL-048/implementations/initial-evaluator-v1/tests -v
```

The scorer's reference is an operator-only JSON object. Labels and future target intervals must never be placed in the model query. The test `fixture()` is a complete generated interface example, not a native packet. Required reference fields are:

| Field | Meaning |
| --- | --- |
| `task_id`, `policy` | `NEURAL-048` and an exact copy of `evaluator.POLICY` |
| `source_manifest_sha256` | Hash of the independently frozen source population/selection/exclusion manifest; not a substitute for validating its content |
| `behavior_history_sha256` | Hash of the frozen shared curvature, velocity, odor-context/history artifact |
| `population_worm_ids`, `evaluation_worm_ids` | Unique selected population and exact scored subset |
| `folds` | Objects with unique `id`, nonempty `train_worm_ids`, possibly empty `validation_worm_ids`, nonempty `test_worm_ids`; each fold partitions the complete selected population, and each evaluation worm appears in test exactly once |
| `episode_inventory` | Every selected scored complete odor/reversal episode: `worm_id`, `session_id`, `episode_id`, all `observation_ids` |
| `observations` | Exactly that inventory: `id`, worm/session/episode IDs, `fold_id`, integer `dorsal`, exact integer `cutoff_ns`, `target_start_ns`, `target_end_ns`; target starts strictly after cutoff |

One biological animal must retain one worm ID across sessions and across duplicate source representations. Hash binding and declared inventories cannot establish this from an unverified native source. Physical observations sharing worm/session/cutoff are rejected even under different observation or episode IDs. Whole-worm fold isolation also isolates its complete episodes; episode keys are scoped to worm and session.

Prediction JSON requires `task_id`, `reference_sha256 = digest(reference)`, `policy_sha256 = digest(POLICY)`, `arm_receipts`, and `predictions`. `digest` hashes canonical compact, key-sorted JSON and rejects nonfinite values. Each prediction is exactly `{id, behavior, neural_history, shifted_neural_history}` with three probabilities. Unknown, missing, duplicated, label-bearing or malformed rows fail before scoring.

Each arm receipt supplies `split_sha256 = digest(reference['folds'])`, the same `behavior_history_sha256` as the reference, its own `frozen_recipe_sha256`, finite nonnegative `cpu_seconds` and integer nonnegative `peak_memory_bytes`. These bind declared shared contexts and record resources; they do not prove that a program actually followed its recipe, respected matched compute, or kept held-out worms out of fitting. Independent execution audit and a frozen resource budget remain required. Empty validation sets are permitted only for an independently frozen recipe requiring no held-out tuning; the scorer does not perform fitting or select recipes.

## Causal history builder

`causal_histories(samples, events, lags_ns, neural_shift_ns, max_age_ns)` is a separate callable that constructs all three matched feature arrays. Each sample supplies worm/session IDs, exact integer `time_ns`, `support_end_ns`, `available_ns`, finite `curvature`, `velocity`, `odor_encounter`, and a nonempty finite `neural` vector. Source time must be no later than support end, which must be no later than availability. All neural channels in a session have fixed width. `support_end_ns` must conservatively cover every upstream transformation, including smoothing, event detection, warping and normalization; a fabricated timestamp does not make a transformation causal.

Events supply `id`, worm/session IDs and `cutoff_ns`. Distinct strictly positive ascending lags select the latest source sample at or before `cutoff - lag`, within a frozen maximum age; sample support and availability must also be at or before that query. The shifted arm uses `cutoff - lag - neural_shift_ns`, with the shift larger than the history span. It retains exactly the same behavioral features. Each pair of selected neural timestamps must differ by the exact shift, including on irregular clocks. No future samples, interpolation, wrapping, cross-session/animal borrowing, padding or silent event dropping are allowed. Insufficient support rejects the complete request. Caller-supplied lag, shift and age policy must be frozen before outcomes; the source does not establish physical nanoseconds for its aligned frames.

This is a positive-lag translation of the source trace, preserving its values and temporal order on the retained segment. It does not claim finite-window empirical autocorrelations remain numerically identical after a boundary crop, and it cannot establish stationarity or eliminate all behavioral confounds. Native control adequacy still requires independent inspection. Event support must be chosen so every frozen event supports both histories.

The scoring CLI does **not** call this builder or certify its output. Its report explicitly separates checked declarative split/coverage/probability/metric properties from unverified actual fitting, causal features and shifted-trace construction. History artifacts and preprocessing lineage must be audited and bound by the operator before a native campaign. This separation prevents an opaque hash receipt from being presented as proof of causal alignment.

## Engineering verification and remaining admission gates

The package tests exercise independent closed-form log-loss/paired interval oracles, unequal worm sizes, class complements, swapped and identical arms, constants, missing/duplicate IDs, complete episode coverage, whole-worm leakage, nonfinite probabilities, exact clocks above floating precision, future support, irregular shifts, cross-session borrowing, CLI execution and malformed JSON. No scientific model was run.

Canonical protocol, native source conversion, complete asset/population identity, odor-crossing alignment, target privacy, rights, authentic signal-derived reference/comparator execution, independent replication and protected scientific admission remain open. Output always reports `runnable_native=false`, `research_qualified=false`, and `submission_ready=false`. Data remain public development only. Upstream code license is GPL-3.0 according to source review; independently authored evaluator source does not copy that code. Nothing here grants dataset redistribution or changes source rights.
