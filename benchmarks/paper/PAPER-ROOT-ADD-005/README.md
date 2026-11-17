# Distributed representations of behaviour-derived object dimensions in the human visual system

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-ROOT-ADD-005`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Success:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule.

**Disposition:** source\_unresolved. The original ordered encoding task and author evaluation route are identifiable, but a comparable numerical source baseline with exact voxel masks, row/session alignment and aggregation has not been recovered. The existing nested image-family ridge evaluator changes the source split and cannot establish a same-task paper win.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition (calibration only)](historical/task.pre-improvement.v1.json)

Existing reproduction graders and pilot scores remain calibration evidence. They cannot establish paper improvement. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 17753 bytes; SHA-256 `1a0fdb922bd45bbbc9f06edd73185278f8dcf655cac8e4754c547492561f1d89`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Binds exact stimulus/voxel identities for all three declared THINGS-fMRI participants and runs prospective nested grouped ridge comparisons across 66 dimensions, category and shape predictors, reporting signed held-out metrics and predictive commonality. Native 12-session encoding / 30-dimension residual partition, exact category/shape recipes, authentic grouping/arrays, protected execution, rights and full-cohort resource/scientific qualification remain unresolved. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/ViCCo-Group/dimension_encoding)
- [Paper](https://www.nature.com/articles/s41562-024-01980-y)
- [Source](https://figshare.com/articles/dataset/20492835)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
