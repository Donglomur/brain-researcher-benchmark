# Functional connectomics reveals general wiring rule in mouse visual cortex

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-FIND-020`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. The legacy wiring-association panels are descriptive, but the same paper also evaluates original image-classification accuracy in Figure 6 and digital-twin fidelity in Extended Data Figure 2. Whole-paper improvement eligibility therefore remains source\_unresolved rather than ineligible. Recover an exact original performance task and baseline before activating it; no new edge-prediction task or local association score is substituted.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 18393 bytes; SHA-256 `3d6b048c68726fabff3d8b131ab647b6d280594c92619cc1a20615654355f3d2`.
- [Preserved legacy runtime declaration](implementations/registered-runtime/manifest.json)
- [Legacy declaration package](implementations/registered-runtime)

This preserved declaration is lineage, not current execution qualification. Its historical paths may describe the source snapshot.

## Implementation artifacts

- [Registered runtime](implementations/registered-runtime) — Calibration only.
  Scope: This is the source package currently selected by the published catalog; current does not assert executable/scientific qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Figure6 components v1](implementations/figure6-components-v1) — Reviewed source component.
  Scope: Figure 6d numerical components. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/cajal/microns-funconn-2025)
- [Paper](https://www.nature.com/articles/s41586-025-08840-3)
- [Source](https://s3.amazonaws.com/bossdb-open-data/iarpa_microns/minnie/functional_data/functional_connectomics/node_and_edge_properties/v1/readme_v1.md)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
