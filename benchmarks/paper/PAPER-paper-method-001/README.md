# Estimating Dimensionality of Neural Representations from Finite Samples

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-001`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. The paper supplies an estimator-comparison problem, but the final-paper numeric risk baseline, complete source panel correspondence and original resampling recipe are not recovered. The existing one-session relative-RMSE grader measures reconstruction of authored reference outputs, not estimator improvement. Biological full-data participation ratio is itself an estimate; increased dimensionality or reduced variation alone cannot establish improved accuracy.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 61202 bytes; SHA-256 `aa9ad951d81a37e4b7820eb27b8fb4987e2dc934a4bcdd365c8cdd993d4a268f`.
- [Preserved legacy runtime declaration](implementations/registered-runtime/manifest.json)
- [Legacy declaration package](implementations/registered-runtime)

This preserved declaration is lineage, not current execution qualification. Its historical paths may describe the source snapshot.

## Implementation artifacts

- [Registered runtime](implementations/registered-runtime) — Calibration only.
  Scope: This is the source package currently selected by the published catalog; current does not assert executable/scientific qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Dimensionality programme](implementations/dimensionality-programme) — Calibration only.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Released synthetic v1](implementations/released-synthetic-v1) — Reviewed source component.
  Scope: Released synthetic example calibration component. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://arxiv.org/abs/2509.26560)
- [Code](https://doi.org/10.25378/janelia.6845348.v4)
- [Code](https://gin.g-node.org/paolo_papale/TVSD/)
- [Code](https://github.com/badooki/dimensionality)
- [Code](https://github.com/badooki/dimensionality/blob/f18de35818502744329f7c92bb17a80af8f48549/legacy/biology/on_Stringer.ipynb)
- [Code](https://openneuro.org/datasets/ds004192)
- [Code](https://proceedings.iclr.cc/paper_files/paper/2026/hash/9768645621c2cd6c5b851a06205b92cf-Abstract-Conference.html)
- [Code](https://raw.githubusercontent.com/badooki/dimensionality/f18de35818502744329f7c92bb17a80af8f48549/LICENSE)
- [Code](https://raw.githubusercontent.com/badooki/dimensionality/f18de35818502744329f7c92bb17a80af8f48549/README.md)
- [Paper](https://proceedings.iclr.cc/paper_files/paper/2026/hash/9768645621c2cd6c5b851a06205b92cf-Abstract-Conference.html)
- [Source](https://figshare.com/articles/dataset/6845348)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
