# Spike inference from calcium imaging data acquired with GCaMP8 indicators

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-047`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Success:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule.

**Disposition:** source\_unresolved. Spike inference has ordered ground-truth metrics, but the original Figure1 cohort/score and excluded-neuron author models are not recovered for the registered117-file panel. Smoothing/timing and paper-era versus corrected software differ. No numeric paper baseline or same-task win can be inferred from the released-panel controller or a generic pretrained CASCADE checkpoint.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition (calibration only)](historical/task.pre-improvement.v1.json)

Existing reproduction graders and pilot scores remain calibration evidence. They cannot establish paper improvement. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 332185 bytes; SHA-256 `e76bf1f26ac0a2da5b12916b4300bc327d3d41c53b85f072d0200a97491673b6`.
- [Preserved legacy runtime declaration](implementations/registered-runtime/manifest.json)
- [Legacy declaration package](implementations/registered-runtime)

This preserved declaration is lineage, not current execution qualification. Its historical paths may describe the source snapshot.

## Task documentation

- [Source recovery notes](docs/transitive-recovery.md)

## Implementation artifacts

- [Registered runtime](implementations/registered-runtime) — Calibration only.
  Scope: This is the source package currently selected by the published catalog; current does not assert executable/scientific qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/HelmchenLabSoftware/Cascade)
- [Code](https://github.com/PTRRupprecht/CascadeTorch)
- [Code](https://raw.githubusercontent.com/HelmchenLabSoftware/Cascade/1f9f98bf93b9b554ab68d6304aa365ab7c7ee34f/LICENSE)
- [Code](https://raw.githubusercontent.com/HelmchenLabSoftware/Cascade/1f9f98bf93b9b554ab68d6304aa365ab7c7ee34f/README.md)
- [Code](https://www.nature.com/articles/s41592-026-03183-x)
- [Code](https://www.nature.com/articles/s41592-026-03183-x.pdf)
- [Paper](https://www.nature.com/articles/s41592-026-03183-x)
- [Source](https://github.com/HelmchenLabSoftware/Cascade/tree/1f9f98bf93b9b554ab68d6304aa365ab7c7ee34f/Ground_truth)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
