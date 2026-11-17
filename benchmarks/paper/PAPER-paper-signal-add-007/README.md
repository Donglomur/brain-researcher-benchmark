# Modelling neural coding in the auditory midbrain with high resolution and accuracy

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-signal-add-007`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Design ready
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** design\_ready. The original Fig. 4b,d prediction task, public evaluation dataset, metric equations and reported per-sound values are recoverable. Exact masking/aggregation, baseline execution and development-data access are incomplete; the historical held-sound improvement program changes the source split and cannot produce the requested paper win.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 17042 bytes; SHA-256 `39a5cd9179a5c6cd1f824709a45a4dec20c2f281bc2f4ca8df32191cbfdf2575`.
- [Preserved legacy runtime declaration](implementations/registered-runtime/manifest.json)
- [Legacy declaration package](implementations/registered-runtime)

This preserved declaration is lineage, not current execution qualification. Its historical paths may describe the source snapshot.

## Implementation artifacts

- [Registered runtime](implementations/registered-runtime) — Calibration only.
  Scope: This is the source package currently selected by the published catalog; current does not assert executable/scientific qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Source equations v1](implementations/source-equations-v1) — Reviewed source component.
  Scope: ICNet original Fig. 4 source-equation scorer. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/fotisdr/ICNet)
- [Paper](https://www.nature.com/articles/s42256-025-01104-9)
- [Source](https://zenodo.org/records/12636772)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
