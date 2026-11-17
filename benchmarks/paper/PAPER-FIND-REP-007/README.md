# Unsupervised pretraining in biological neural networks

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-FIND-REP-007`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. Whole-paper review identifies an original input-to-neural-response fitting procedure in Methods Retinotopy: a fixed 200-kernel convolutional encoding model. This source-native reconstruction route warrants further recovery, but the original evaluated performance endpoint/panel, exact score and meaningful fixed-capacity comparison are unverified. A preprocessing optimizer alone cannot activate an improvement task. Figure 5 mouse learning and descriptive neural contrasts remain distinct; no artificial pretraining experiment or new held-out benchmark is asserted.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 31228 bytes; SHA-256 `37289aacfc669bb0fc4dd17dc18df8cc49515b00a69e8ec9476e2b11b8ea30a6`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Complete supplied-session all-cell stimulus selectivity, pinned-code sequence similarity, reward-predictive activity, reward-zone licking and longitudinal animal summaries. Authentic experiment-info-derived population/transforms, native preprocessing and parity, matched source controls, protected targets, rights/exposure and scientific qualification remain held; the sequence paper/code disagreement is explicit. Coding-direction and density-map endpoints remain outside this component, and shared source families with NEURAL-027/028 are not independent cohorts. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/MouseLand/zhong-et-al-2025)
- [Paper](https://doi.org/10.1038/s41586-025-09180-y)
- [Source](https://janelia.figshare.com/articles/dataset/Unsupervised_pretraining_in_biological_neural_network/28811129)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
