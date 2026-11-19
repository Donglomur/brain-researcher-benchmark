# Continuous outcomes with official code and released models

This version compares `paper_data` with `paper_data_author_code_and_weights` under the same `PAPER-SMC-RNN-2024` benchmark ID. Both conditions receive identical original observations, permitted validation labels, paper, scientific task and per-outcome resource profiles. The assisted condition additionally receives the pinned official source and exactly ten published model/configuration/history files totaling **3,496,380 bytes**. This measures the combined benefit of official code and pretrained assets; it does not isolate code alone.

The accepted source-only version in `../continuous-outcomes-v1` remains unchanged as history and an optional separately named ablation. Its manifests must not be renamed into version 2. No new benchmark ID, result or successful reproduction is created by adding this access condition.

## Scientific meaning

The continuous measurements and original numerical evaluator are unchanged. Reproduction retains both named source methods, the original 192 particles × 32 repeats with `smooth=false`, and all eight findings. Reports contain separate published/current-release values and signed/absolute differences without an equivalence threshold or averaging. Faithfully running released-model inference is an allowed reproduction route in the assisted condition. It is not independent training or native neural understanding. An independently authored faithful implementation remains allowed.

Improvement uses one complete offline prediction with all four metrics. All 35 same-trial observed held-in bins may inform it; source-method receptive fields are not restrictions on that primary offline candidate. Reports retain every SMC reference, the strongest retained SMC co-bps reference, companion tradeoffs, complete LFADS/NDT published vectors and a separate candidate-minus-NDT co-bps difference. Exceeding SMC alone is not exceeding the strongest published paper comparison or achieving SOTA.

The outputs are fixed-panel point measurements. Biological generalization and source/candidate seed variation are not estimated. There is no new binary pass, superiority margin, confidence interval or final-target resampling. Released weights do not prove exact historical training inputs, seeds, checkpoint-to-paper-row linkage or absence of undocumented upstream exposure. The original test panel is publicly exposed, not an untouched holdout.

## Exact assets and protected evaluator inputs

`asset_allowlist.json` is the public projection of the independently reviewed official Git identities. It includes the four learned state dictionaries and six configuration/history files required by the original loader. The latter are not asserted to be pure weight tensors. Every path, role, size and SHA256 must also match the original pinned source manifest; unknown models, arbitrary pickle files or unrestricted checkpoint directories are not allowed.

Assisted packets contain `official_asset_manifest.json` and the ten files beneath `official_source/` at their original relative paths. `official_source_manifest.json` continues to describe only the separately pinned source files. Original test targets, operator predictions/calibration arrays, unknown assets and early final-test feedback remain excluded. The unassisted packet receives neither author source nor assets.

Preparation and inspection read opaque asset bytes only to authenticate size and hashes. Freeze and score operate on numerical HDF5 predictions; they never deserialize checkpoints. The original model loader uses unrestricted serialization. Future loading belongs in an isolated participant or separately admitted author-model process without operator targets, credentials or writable evaluator state. A matching artifact hash does not prove execution safety.

## Operator commands

`benchmark.py` provides the same four explicit stages as version 1: `prepare`, `inspect`, `freeze`, and `score`. Use an existing environment with NumPy, SciPy, scikit-learn and h5py. No model, Torch loader or installation is invoked. `--help` documents required paths and byte bounds.

The trusted current task selects `continuous_outcomes_v2`, version `2`, the exact `policy.json` SHA256, and entrypoint `implementations/continuous-outcomes-v2/benchmark.py`. The [current construction-status note](../../docs/current-source-status-20261118.json) confirms adoption and the independently verified initial 71-file, 31,393,479-byte paired export for that exact task identity. `TASK_AMENDMENT.json`, `proposed-task.json`, and proposal-phase wording within the frozen task preserve their original history; the status note identifies the superseded clauses without changing the material binding. Only the integration owner changes canonical task/registry/CLI/catalog bindings.

Provide a budget JSON with exactly `reproduction` and `improvement`, each containing positive integer `cpu_seconds`, `wall_seconds`, `memory_bytes` and `threads`. Each outcome's profile is matched across access conditions. Equal caps do not imply equal compute requirements or validated training feasibility. The 75,000 CPU-second reproduction profile was informed by roughly 60,720 CPU seconds of released-weight reference inference; it does not prove every original script fits 4 GiB or that independently training weights fits this allowance. Agent/model budgets and enforcement remain separately controlled for any future episode.

Using explicit operator variables, prepare and inspect a fresh external packet:

```sh
"$PYTHON" "$ENTRY" prepare \
  --prepared-root "$PREPARED" --author-source "$AUTHOR" --paper "$PAPER" \
  --task "$TASK" --task-sha256 "$TASK_SHA" --budget "$BUDGET" \
  --output "$PAIR_DIR" --max-bytes "$PAYLOAD_CAP" --reserve-bytes 64424509440

"$PYTHON" "$ENTRY" inspect \
  --pair "$PAIR_DIR/pair_manifest.json" --pair-sha256 "$PAIR_SHA" \
  --task "$TASK" --task-sha256 "$TASK_SHA" --max-bytes "$PAYLOAD_CAP"
```

Choose the payload cap from the reviewed complete byte plan; do not assume that adding assets fits an old cap. The exporter refuses existing output, changed assets, unsupported roles and exceeded bounds. The inspector validates the entire physical inventory and source-native panels, not just manifest labels. Rehashed missing/extra assets, substituted roles, target/prediction payloads, unknown model paths, symlinks and changed condition contents must fail.

## Per-method usage and final predictions

Declarations use schema `smc_continuous_submission_declaration_v2`. The top-level fields remain `schema`, `role`, `method_id`, `outcome`, `condition` and `methods`. A method contains:

- `source_sha256`: SHA256 of the actual participant program source.
- `seed`: a nonnegative integer.
- `recipe`: the original recipe object for participant reproduction; otherwise `null`.
- `behavior_guided_fitting` and `behavior_guided_selection`: actual booleans.
- `asset_usage`: the actual per-asset usage records below.

For `paper_data`, `asset_usage` must be `[]`. For the assisted condition, it must contain exactly one entry for each of the ten delivered manifest paths, with the exact `path` and `sha256`, plus boolean `loaded`, `adapted`, `fine_tuned`, `retrained` and `replaced`. Set flags from what actually happened. Availability alone is not loading. Adaptation/fine-tuning requires declared loading; retraining or replacement can be declared without loading the released parameters. Generated `construction_control` submissions keep every asset flag false and do not claim authentic model execution. All declarations remain unverified execution claims until suitable evidence is supplied.

A reproduction submission jointly freezes `causal` and `noncausal`; improvement freezes only `offline`. The unchanged HDF5 interface requires all six original complete-panel arrays, with the two train-forward arrays optional. Predictions must be finite nonnegative expected spike counts per 20-ms bin, preserving original trial/neuron/bin order.

```sh
"$PYTHON" "$ENTRY" freeze \
  --pair "$PAIR_DIR/pair_manifest.json" --pair-sha256 "$PAIR_SHA" \
  --task "$TASK" --task-sha256 "$TASK_SHA" --max-bytes "$PAYLOAD_CAP" \
  --condition paper_data_author_code_and_weights --outcome improvement \
  --submission "offline=$PREDICTION" --declaration "$DECLARATION" --output "$FREEZE"

"$PYTHON" "$ENTRY" score \
  --pair "$PAIR_DIR/pair_manifest.json" --pair-sha256 "$PAIR_SHA" \
  --task "$TASK" --task-sha256 "$TASK_SHA" --max-bytes "$PAYLOAD_CAP" \
  --frozen "$FREEZE" --frozen-sha256 "$FREEZE_SHA" \
  --condition-root "$PAIR_DIR/paper_data_author_code_and_weights" \
  --target "$OPERATOR_TARGET" --evaluator "$ORIGINAL_EVALUATOR" \
  --scratch-bytes "$SNAPSHOT_CAP" --output "$RESULT"
```

Freeze reads no test target. Score snapshots every complete committed prediction before first target access, then runs the unchanged original evaluator and emits one atomic report without replacing earlier output. Operator records and scratch stay outside participant materials. The operator must enforce one final submission, the declared access/budgets and isolation; this interface does not claim a hostile-code sandbox.

An AI attempt is not required to construct a valid runnable benchmark. Definition adoption and the recorded initial material preparation are complete for the unchanged task identity. Protected participant execution and runtime enforcement remain separately unqualified. A new export still requires its own authentication and inspection; the existing material receipt does not validate another payload. AI attribution, faithful execution and scientific performance require future submission evidence; author calibration and generated controls are not AI results.
