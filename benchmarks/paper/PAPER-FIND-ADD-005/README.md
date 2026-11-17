# Encoding of cerebellar dentate neuron activity during visual attention in rhesus macaques

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-FIND-ADD-005`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Success:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule.

**Disposition:** source\_unresolved. The original GLM has an ordered cross-validated likelihood objective, but its comparable numeric performance baseline and cohort-level reduction were not recovered. The reported modulation indices and fractions of significantly decodable cells describe biology and cannot become quantities to maximize. The local ridge/eye-covariate, blocked-fold conditional gap-direction score changes the source comparison.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition (calibration only)](historical/task.pre-improvement.v1.json)

Existing reproduction graders and pilot scores remain calibration evidence. They cannot establish paper improvement. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 14324 bytes; SHA-256 `e797b5f91fb74da5e7b5f7a73a96b7ab0798a38a063d0787abeaf43b8c471a72`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Prospective within-cell dentate encoding from exported spike/event/eye/history trials through source-informed binning and event kernels, paired ridge Poisson models, nested contiguous trial-block fitting and held-out likelihoods. The implemented contrast is gap-direction encoding conditional on event/eye/history/saccade terms; direct attention and behavioral decoding remain unresolved. Authentic MAT/population reconciliation, native hierarchical MATLAB model parity, figure targets, protected evaluation and scientific qualification remain held. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/sakoay/ErasmusAttn_2020)
- [Paper](https://elifesciences.org/articles/99696)
- [Source](https://datadryad.org/dataset/doi:10.5061/dryad.1rn8pk14s)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
