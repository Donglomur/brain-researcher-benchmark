# Continuous original-panel outcomes

This component makes the SMC task a continuous measurement benchmark. It prepares current participant materials, inspects their exact allowed contents, freezes a complete final submission, and invokes the unchanged original NLB evaluator. It does not require a fabricated numerical tolerance or an AI attempt to construct the benchmark.

`policy.json` records the root-adopted scientific policy. Reproduction measures the two named source methods and all eight findings separately. Improvement measures one complete offline prediction and all four original metrics. The two access conditions are `paper_data` and `paper_data_author_code`; their paper, task, allowed observations and resource settings are identical. Only the latter receives the pinned official source. No author checkpoint, operator prediction or original test target is delivered.

## What the scores mean

For reproduction, the report gives each original metric with its published value, corresponding current-release reference, signed difference and absolute discrepancy. There is no arm averaging, equivalence margin or binary reproduction pass. A participant declaring this source-method route retains the original 192 particles × 32 repeats, `smooth=false`, and source-method dependencies. An independently authored faithful implementation is allowed. A declaration does not prove execution fidelity.

For improvement, all 35 supplied held-in bins from the same trial may inform a single offline candidate. The source methods' different receptive fields are not restrictions on this primary offline candidate. The report retains all four SMC reference vectors and every companion difference. Its selected SMC reference is the complete current-release noncausal vector beginning at co-bps **0.3410160879591172**. It separately reports the source paper's complete LFADS and NDT vectors, including candidate-minus-NDT co-bps relative to **0.3597**. A gain over SMC alone is not a gain over the paper's best reported comparison and is not a SOTA claim. Negative companion differences remain visible.

These are fixed-panel point measurements conditional on the frozen predictions. Biological generalization and source/candidate seed uncertainty are not estimated. No confidence intervals, target resampling, superiority margins or binary wins are introduced. Original test targets were publicly released in January 2026; local exclusion cannot create an untouched holdout. Later LangevinFlow/MINT context retains its documented attribution and limitations, without implying a new frontier survey.

The retained full author calibration is reference evidence. The failed noncausal supervisor record remains failed; its independently authenticated completed scalar output is a separate accepted artifact. Neither calibration vector is an AI attempt or proof of exact historical checkpoint/data identity.

## Operator sequence

Use an environment with the existing NumPy, SciPy, scikit-learn and h5py dependencies. No dependency installation, participant execution or download is performed by these commands. Paths below are explicit operator inputs; material outputs belong outside Git worktrees. `PYTHON` identifies that existing interpreter and `ENTRY` this `benchmark.py`.

Before preparing materials, the canonical task must select this route with:

```json
"continuous_outcomes_v1": {
  "version": 1,
  "policy_sha256": "1e04f61dedded47ed5de763bb328d2aa15dc2c26e3869b76f68d9af51fea61d0",
  "entrypoint": "implementations/continuous-outcomes-v1/benchmark.py"
}
```

The operator supplies the exact trusted SHA256 of that adopted task file. This prevents old definitions from silently passing as current materials. Historical task/contract files remain unchanged in their retained lineage; their older acceptance instructions are not exported as the current participant task.

Create a resource JSON object with exactly `reproduction` and `improvement`, each containing positive integer `cpu_seconds`, `wall_seconds`, `memory_bytes`, and `threads`. Each outcome's CPU program budget is identical across access conditions; the two outcomes may have different profiles. Select values for the intended episode before preparation. A low-memory short run cannot be assumed adequate for the original 192×32 source method: the completed reference execution used roughly 60,720 CPU seconds and its original scorer exceeded 1 GiB RSS. Training adequacy remains separate. Agent/model token and access budgets and enforcement, where applicable, must be separately controlled by the episode operator. Preparation and inspection do not enforce runtime isolation or resource limits, and profile values do not authorize execution.

```sh
"$PYTHON" "$ENTRY" prepare \
  --prepared-root "$PREPARED" --author-source "$AUTHOR" --paper "$PAPER" \
  --task "$TASK" --task-sha256 "$TASK_SHA" --budget "$BUDGET" \
  --output "$PAIR_DIR" --max-bytes 33554432 --reserve-bytes 64424509440
```

The prepared root contains admitted `mc_maze/test` and `mc_maze/val` tensors and native panel metadata. Existing authentic inputs may be reused; old participant manifests must not be renamed into this schema. Preparation validates the unchanged source tensor content, original paper and source allowlist, writes a bounded fresh pair, and runs the same inspector before installation. It refuses existing output, mismatched source data and exceeded byte/disk bounds.

Record the newly created pair manifest SHA256 as `PAIR_SHA`, then inspect it against the same trusted task:

```sh
"$PYTHON" "$ENTRY" inspect \
  --pair "$PAIR_DIR/pair_manifest.json" --pair-sha256 "$PAIR_SHA" \
  --task "$TASK" --task-sha256 "$TASK_SHA" --max-bytes 33554432
```

Inspection validates the entire exact inventory, current policy and instructions, both source-native panel identities, shared allowed inputs and code-only additions. Symlinks, special files, extra files or metadata, obsolete schemas, altered budgets and altered delivered bytes are rejected. The result reports material/interface validity separately from execution and AI attribution. It does not count an unattempted outcome as a failed benchmark.

## Final submissions

Each prediction HDF5 contains group `mc_maze_20` and all six required original rate arrays; the two original train-forward arrays are optional. The actual public panel lists their complete shapes. All arrays contain finite nonnegative expected spike counts per 20-ms bin in original trial/neuron/bin order. Partial panels, extra groups, indirect HDF5 storage and changed arrays are rejected.

Supply a declaration with exactly these fields. `methods` contains both `causal` and `noncausal` for reproduction, or only `offline` for improvement. Each method declares the SHA256 of its actual program source, seed and actual use of behavior-guided fitting and selection. Source identities and use declarations are recorded, not authenticated as execution provenance by this tool.

```json
{
  "schema": "smc_continuous_submission_declaration_v1",
  "role": "participant",
  "method_id": "operator-assigned-method-id",
  "outcome": "improvement",
  "condition": "paper_data",
  "methods": {
    "offline": {
      "source_sha256": "ACTUAL_64_CHARACTER_SOURCE_SHA256",
      "seed": 0,
      "recipe": null,
      "behavior_guided_fitting": false,
      "behavior_guided_selection": false
    }
  }
}
```

A participant reproduction declaration instead gives each arm `"recipe": {"particles": 192, "repeats": 32, "smooth": false}`. A generated implementation control uses role `construction_control` and `recipe: null`, so it never asserts it ran the authentic source recipe. Construction-control measurements are not AI outcomes.

Freeze improvement with one prediction, or reproduction with two `--submission` arguments (`causal=...` and `noncausal=...`). A single joint reproduction submission contains both arms; it is not two independent opportunities to inspect test feedback.

```sh
"$PYTHON" "$ENTRY" freeze \
  --pair "$PAIR_DIR/pair_manifest.json" --pair-sha256 "$PAIR_SHA" \
  --task "$TASK" --task-sha256 "$TASK_SHA" --max-bytes 33554432 \
  --condition paper_data --outcome improvement \
  --submission "offline=$PREDICTION" --declaration "$DECLARATION" --output "$FREEZE"
```

Freeze reads no original test target. It binds the actual complete prediction bytes, current materials, outcome, condition and typed declarations. Every output is created atomically without replacement. Operator records and score scratch space must remain outside the participant pair. The operator must enforce one final submission per outcome and prevent test feedback, extra observations or cross-test-trial adaptation; this cooperative interface is not a hostile-code sandbox.

In a separate trusted scoring process, provide the unchanged original test target and evaluator. The scorer snapshots **all** committed submissions within the cumulative scratch cap before first target access. It revalidates complete shape/content and source identity, computes the original metrics and writes one complete report. Insufficient scratch, changed bytes or a missing arm fails before target scoring.

```sh
"$PYTHON" "$ENTRY" score \
  --pair "$PAIR_DIR/pair_manifest.json" --pair-sha256 "$PAIR_SHA" \
  --task "$TASK" --task-sha256 "$TASK_SHA" --max-bytes 33554432 \
  --frozen "$FREEZE" --frozen-sha256 "$FREEZE_SHA" \
  --condition-root "$PAIR_DIR/paper_data" --target "$OPERATOR_TARGET" \
  --evaluator "$ORIGINAL_EVALUATOR" --scratch-bytes "$SNAPSHOT_CAP" --output "$RESULT"
```

The evaluator may be the retained `source-matched-nlb-v1/third_party/nlb_tools_0_0_3/evaluation.py` or the exact original source bytes. The target must match the fixed original target hash. AI attribution, actual resource/access compliance and faithful source-method execution require suitable per-submission evidence. Those requirements are distinct from completing and validating the runnable continuous benchmark.

## Retained lineage and validation

This package is additive. `source-matched-nlb-v1`, `offline-nlb-outcomes-v1`, `paired-reproduction-v1` and their historical contracts remain byte-preserved. The new entrypoint reuses pinned low-level source validators and bounded I/O, and the unchanged evaluator; it does not fabricate old hash-only review gates or relabel calibration.

`TASK_AMENDMENT.json` is an exact proposal for the integration owner, not a self-applied canonical rewrite. Fresh authentic-material preparation and adopted current selectors remain required before claiming current construction closure. Generated controls test the operator path and comparisons; they do not constitute new authentic model or AI results.
