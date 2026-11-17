# A geometric shape regularity effect in the human brain

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-ROOT-ADD-010`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Success:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule.

**Disposition:** source\_unresolved. The paper has a legitimate same-task oddball AUROC endpoint with explicit run-held-out folds, but the exact published numeric baseline and source-matched summary have not been recovered. The current evaluator computes RSA only, so its reconstruction cannot establish a decoding improvement.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition (calibration only)](historical/task.pre-improvement.v1.json)

Existing reproduction graders and pilot scores remain calibration evidence. They cannot establish paper improvement. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 226208 bytes; SHA-256 `ce1c9c515c100f4287574cdc7775c8b586b091eecc5fd8b8ae0a5b981874ca45`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Processed-reference sensor-RSA path with run-crossvalidated dissimilarities, symbolic/CORnet-S covariance-weighted correlations, both smoothing branches and exact 20-participant/158-run structural coverage; optional cleaned-epoch export and source temporal-test adapters are included. Raw BIDS preprocessing, historical decoding, native dependency and model identity parity, reviewed-preprint-to-Version-of-Record reconciliation, noise ceiling, authentic references and protected qualification remain open. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/mathias-sm/AGeometricShapeRegularityEffectHumanBrain)
- [Paper](https://doi.org/10.7554/eLife.106464.3)
- [Paper](https://elifesciences.org/articles/106464)
- [Source](https://openneuro.org/datasets/ds006012/versions/1.0.1)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
