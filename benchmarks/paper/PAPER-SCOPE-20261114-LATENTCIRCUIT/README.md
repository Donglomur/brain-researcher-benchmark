# Latent circuit inference from heterogeneous neural responses during cognitive tasks

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-SCOPE-20261114-LATENTCIRCUIT`
- **Track:** Paper research
- **Registration:** Expansion draft
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. Published monkey-specific projected-fit anchors exist, but the original empirical population, projection/error normalization and model-to-neural adapter are not recovered as one verified comparison. Historical half-trial membership may be recovered or replaced by a documented source-conformant stochastic rerun under the original protocol, with calibration and paired candidate-author scoring. The current fixed-original-neuron scorer changes the metric and uses a nested split; that is an extension.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 12466 bytes; SHA-256 `fc969988b966370ded695bdcb9a95c9436478578be75c9f5aebe00ab8568581c`.
- [Registration and provenance](../../../docs/provenance/registrations/expansion-20261114/registry.json)

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)
- [source reconciliation v2](docs/source-reconciliation-v2.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Owner-side fixed-neuron held-trial loss arithmetic for both monkeys and all 72 conditions, train-only normalization, declared-census/split audits and a condition-mean control. Native timing/objective correspondence, authentic unit census, full 200-start reference, behavioral non-inferiority and protected execution remain held, including residual correctness inference from eligibility/counts. Scientific qualification is unknown. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Paper](https://www.nature.com/articles/s41593-025-01869-7)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
