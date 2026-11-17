# Complete LangevinFlow NLB panel: structural guard

This component checks the complete original eight-condition prediction interface and delegates numerical scoring to the byte-pinned official NLB evaluator. It prevents an omitted dataset or companion metric from being reported as complete. It is **not yet a qualified paper benchmark**, and it makes no reproduction, improvement or SOTA decision.

The selected original result is Tables 1, 2, 4 and 5 of [Langevin Flows for Modeling Neural Latent Dynamics](https://arxiv.org/html/2507.11531v2). All four datasets at both resolutions remain required; this is one paper panel, not eight new paper tasks.

| Dataset | Required groups | Observed bins, 5/20 ms | Forward bins, 5/20 ms | Required metrics |
|---|---|---:|---:|---|
| MC_Maze | `mc_maze`, `mc_maze_20` |140/35|40/10|co-bps, vel R2, psth R2, fp-bps|
| MC_RTT | `mc_rtt`, `mc_rtt_20` |120/30|40/10|co-bps, vel R2, fp-bps|
| Area2_Bump | `area2_bump`, `area2_bump_20` |120/30|40/10|co-bps, vel R2, psth R2, fp-bps|
| DMFC_RSG | `dmfc_rsg`, `dmfc_rsg_20` |300/75|40/10|co-bps, tp corr, psth R2, fp-bps|

Each submission group must contain the six original author fields: `train_rates_heldin`, `train_rates_heldout`, `eval_rates_heldin`, `eval_rates_heldout`, `eval_rates_heldin_forward`, `eval_rates_heldout_forward`. Axes are trial×time×unit; rate units are expected spike counts **per bin**, with no Hz conversion. MC_RTT PSTH is inapplicable, so the complete output has thirty metric cells.

Time axes derive from original source windows. Authentic trial/unit counts and ordered identities have not been qualified. The target-blind freeze checks internal dimensions and labels its result `source_structure_only`; a smaller self-consistent file does not thereby become a complete authentic panel. Scoring additionally matches axes to the pinned original target file, but its report still marks scientific and authentic case qualification unestablished. Complete original input preparation and ordered trial/unit provenance remain necessary.

The guard does not clip, impute, reorder, rescale or apply global finite-value rejection. Original DMFC set-to-go NaNs, behavior-invalid bins, condition memberships, jitter and Area2's two decoder masks remain unchanged. Value-level validity and every metric computation belong to the original evaluator. Its thirty aggregate values must be finite to produce a complete report. Additional official target groups are permitted; submitted and returned groups must be exactly the selected eight.

## Source identities and unresolved original recipe

- [Author source](https://github.com/KingJamesSong/LangevinFlow_CCN/tree/68dcbfaa78b2371851842333ae933eea1f961832): `68dcbfaa78b2371851842333ae933eea1f961832`.
- [Official evaluation.py](https://github.com/neurallatents/nlb_tools/blob/42f8410b88e12db136910fa2f888b025ea0aa2ae/nlb_tools/evaluation.py): SHA256 `05f49d3cdf7720ae68e0fb76113a9e450e9df3813c6c6837689f23a9be278476`.
- [Original tensor construction](https://github.com/neurallatents/nlb_tools/blob/42f8410b88e12db136910fa2f888b025ea0aa2ae/nlb_tools/make_tensors.py): SHA256 `e79badd983e37fa0c8f0ddbdeb74972ed505ba4672035daca4e8af16a7bc2d9d`.
- [Released test-target pointer](https://github.com/neurallatents/nlb_tools/blob/42f8410b88e12db136910fa2f888b025ea0aa2ae/data/eval_data_test.h5): 105,927,616 bytes, SHA256 `f2f434d30193251b58e6a693381fdd185c8fbc0e47d38f8810e65295bc42c865`. Only pointer metadata was authenticated during construction; actual target arrays and all eight target schemas remain uninspected here.

The official numerical evaluator is neither bundled nor rewritten. The loader hashes and executes the same byte string to avoid a source hash followed by a different file read. Numerical dependency versions are reported; this does not prove equivalence of the original author environment. The loader pattern follows the existing [SMC operator scorer](../../../paper/PAPER-SMC-RNN-2024/implementations/source-matched-nlb-v1/scorer.py), while its single-condition counts and finite-all gate are not imported into this task.

Current author code uses two attention heads, whereas both manuscript versions state four. It discards the new instance returned by Lightning 1.6.0's best-checkpoint loader and continues with the supplied post-fit instance; the call may also affect random state. Published checkpoint/configuration provenance and the complete 5 ms settings remain unresolved. This guard changes none of those scientific choices. The original author producer averages 50 stochastic **log-rate** predictions and then exponentiates; averaging rates is different. Improved methods may use a different architecture or inference procedure under a separately fixed same-task information and compute budget. Reproduction must first resolve the original recipe.

## Operator interface

Run from the repository root with Python 3.11+. Freeze needs h5py; scoring additionally needs the original evaluator's NumPy, SciPy and scikit-learn dependencies. Nothing is installed automatically. Supply an explicit submission byte allowance derived from the actual prepared panel; no trial-count or file-size default substitutes for authentic preparation.

```sh
python3 -I -B benchmarks/shared/langevinflow/complete-nlb-panel-v1/guard.py freeze \
  --submission /operator/predictions.h5 --output /operator/prediction-freeze.json \
  --max-submission-bytes "$SUBMISSION_BYTE_LIMIT"

python3 -I -B benchmarks/shared/langevinflow/complete-nlb-panel-v1/guard.py score \
  --submission /operator/predictions.h5 --freeze /operator/prediction-freeze.json \
  --target /evaluator/eval_data_test.h5 --scorer-source /evaluator/evaluation.py \
  --output /operator/scores.json --max-submission-bytes "$SUBMISSION_BYTE_LIMIT"
```

`freeze` accepts no target path. `score` validates frozen submission bytes and shapes before opening targets, makes a bounded private submission snapshot, verifies original source/target hashes and delegates once. Existing records are never overwritten. The byte allowance bounds submission hashing and its additional snapshot; it is not a memory or time limit. Future authentic scoring must run under an independently approved outer process/RAM/wall budget adequate for the complete panel and original ridge fits. The current generated-control budget is not an estimate of scientific execution cost.

Targets became public in January 2026. An operator directory, checksum, or freeze record is not a hostile-code sandbox. Actual participant execution must prevent access to targets, joins and online target downloads through enforced runtime isolation. Target access follows the relevant study's complete prediction-freeze policy; this component does not grant permission to stage targets or launch a study.

## Generated controls

```sh
python3 -I -B benchmarks/shared/langevinflow/complete-nlb-panel-v1/test_guard.py
```

Controls use tiny constructed arrays/HDF5 files and a recording fake evaluator. They exercise missing fields, mismatched original time/trial/unit axes, required decoder masks, untouched NaNs/order, frozen-byte changes and the operator interface. They never import or execute the official numerical scorer on authentic data. Passing them establishes software behavior only. No current task IDs, registry entries or scientific histories are changed by this shared component.
