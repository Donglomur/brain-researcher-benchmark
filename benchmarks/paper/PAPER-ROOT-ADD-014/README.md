# Precise spatial tuning of visually driven alpha oscillations in human visual cortex

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-ROOT-ADD-014`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. A real ordered source endpoint exists: alpha pRF heldout prediction, including the reported43% median with baseline correction in Fig.7. The original electrode mask and metric implementation are not reconciled with the433-electrode local programme, its prospective equal-person mean, or the portable optimizer. Those local comparisons cannot certify surpassing the original source result.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 24700 bytes; SHA-256 `7f1c0cfc3182f0e40e2aa2675b45b42661274093938935a591e59c768d0d4021`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Implementation artifacts

- [Alpha programme](implementations/alpha-programme) — Calibration only.
  Scope: Keep mixed current/source-predecessor/context members together; this map does not select a new operative version or qualify execution. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Figure7 endpoint v1](implementations/figure7-endpoint-v1) — Reviewed source component.
  Scope: Original Figure 7 endpoint component. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/KenYMB/ECoG_alphaPRF)
- [Paper](https://elifesciences.org/articles/90387)
- [Source](https://openneuro.org/datasets/ds004194/versions/3.0.0)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
