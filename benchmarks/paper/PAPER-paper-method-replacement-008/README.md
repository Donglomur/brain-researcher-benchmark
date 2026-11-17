# BaRISTA: Brain Scale Informed Spatiotemporal Representation of Human Intracranial Neural Activity

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-replacement-008`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. Source classification targets and numeric results are recoverable, but the complete registered paper program includes original reconstruction and spatial-scale/pretraining analyses whose H/checkpoints, exact reconstruction evaluation and authentic split/source-clock bindings remain unresolved. A paper–code session-label discrepancy also needs resolution. The local chronological AUC aggregate or source-amended reconstruction MSE cannot by itself establish surpassing BaRISTA on its original full task.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 47399 bytes; SHA-256 `470c0bb1f3af5a01187f5337d8b3bf22533cb50bf99c002d9c665dcdd16e3b1e`.
- [Preserved legacy runtime declaration](implementations/registered-runtime/manifest.json)
- [Legacy declaration package](implementations/registered-runtime)

This preserved declaration is lineage, not current execution qualification. Its historical paths may describe the source snapshot.

## Implementation artifacts

- [Registered runtime](implementations/registered-runtime) — Calibration only.
  Scope: This is the source package currently selected by the published catalog; current does not assert executable/scientific qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/ShanechiLab/BaRISTA)
- [Code](https://raw.githubusercontent.com/ShanechiLab/BaRISTA/83b27375eba60e9eba9da4e7dd8fb283baace376/barista/config/braintreebank.yaml)
- [Code](https://raw.githubusercontent.com/ShanechiLab/BaRISTA/83b27375eba60e9eba9da4e7dd8fb283baace376/barista/config/model.yaml)
- [Code](https://raw.githubusercontent.com/ShanechiLab/BaRISTA/83b27375eba60e9eba9da4e7dd8fb283baace376/barista/config/train.yaml)
- [Code](https://raw.githubusercontent.com/ShanechiLab/BaRISTA/83b27375eba60e9eba9da4e7dd8fb283baace376/barista/prepare_segments.py)
- [Code](https://raw.githubusercontent.com/ShanechiLab/BaRISTA/83b27375eba60e9eba9da4e7dd8fb283baace376/barista/train.py)
- [Code](https://raw.githubusercontent.com/ShanechiLab/BaRISTA/83b27375eba60e9eba9da4e7dd8fb283baace376/barista/utility_scripts/aggregate_runs.py)
- [Code](https://raw.githubusercontent.com/ShanechiLab/BaRISTA/83b27375eba60e9eba9da4e7dd8fb283baace376/barista/utility_scripts/run_finetune_folds.sh)
- [Code](https://raw.githubusercontent.com/ShanechiLab/BaRISTA/83b27375eba60e9eba9da4e7dd8fb283baace376/barista/utility_scripts/run_finetune_random_splits.sh)
- [Source](https://braintreebank.dev/)
- [Source](https://raw.githubusercontent.com/czlwang/PopulationTransformer/d237755bbdea123c60bface0cecbb48bab6f42de/electrode_selections/clean_laplacian.json)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
