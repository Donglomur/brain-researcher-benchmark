# BOLD signal changes can oppose oxygen metabolism across the human cortex

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-signal-add-013`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. Source Figure 5 contains an ordered regression-estimation route: CMRO2 and its task changes are fitted from source hemodynamic inputs with reported stratum-specific R-squared values. This source-native subtask can be investigated independently of the legacy descriptive CALC–CTRL endpoint. Exact native row/mask/model binding and a scientifically valid improvement criterion remain unresolved: CMRO2 is itself derived from these inputs through Fick’s principle, so increasing fitted R-squared may only reconstruct a known identity and cannot by itself establish better physiological estimation.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 18351 bytes; SHA-256 `aa3f20e5085adb38cecfc5ee18e1c7ede4b59bd750d660de0d24bc3fc1329a3b`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Computes the fixed 40-participant CALC-CTRL map contrast, corrected primary and explicitly mixed-lineage original sensitivity, distinct source median reductions and descriptive paired-participant summaries. Authentic maps/masks/geometry, physiological correction, native PLS, figure parity, geometry-preserving spatial nulls, protected references and scientific qualification remain held; data CC0 and upstream code CC BY-NC-SA 4.0 terms remain distinct. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Figure5 baseline v1](implementations/figure5-baseline-v1) — Reviewed source component.
  Scope: Figure 5 baseline regressions. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/NeuroenergeticsLab/two_modes_of_hemodynamics)
- [Paper](https://www.nature.com/articles/s41593-025-02132-9)
- [Source](https://openneuro.org/datasets/ds004873/versions/2.0.6)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
