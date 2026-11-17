# Latent circuit inference from heterogeneous neural responses during cognitive tasks

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-SCOPE-20261114-LATENTCIRCUIT`
- **Track:** Paper research
- **Registration:** Expansion draft
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Separate paper outcomes

The current definition supports two independent outcomes: recreate the original findings and exceed them on the same task. Each uses matched paper+data and paper+data+author-code conditions. Contract eligibility and declared protocol availability do not establish a delivered runtime or scientific result.

- [Original-finding reproduction contract](reproduction.v1.json)
- [Paired outcome protocols](outcomes.v1.json)
- [Preserved definition before dual outcomes](historical/task.pre-outcomes.v1.json)

| Outcome | Information condition | Endpoint eligibility | Protocol status | Declared availability | Scientific outcome |
| --- | --- | --- | --- | --- | --- |
| Reproduction | Paper data | source\_unresolved | unresolved | unresolved | Unknown |
| Reproduction | Paper data author code | source\_unresolved | unresolved | unresolved | Unknown |
| Improvement | Paper data | source\_unresolved | unresolved | unresolved | Unknown |
| Improvement | Paper data author code | source\_unresolved | unresolved | unresolved | Unknown |

Author-baseline replay and historical reconstruction attempts retain their original scopes. They are not promoted to qualified AI reproductions or improvements by these contracts.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. Published monkey-specific projected-fit anchors exist, but the original empirical population, projection/error normalization and model-to-neural adapter are not recovered as one verified comparison. Historical half-trial membership may be recovered or replaced by a documented source-conformant stochastic rerun under the original protocol, with calibration and paired candidate-author scoring. The current fixed-original-neuron scorer changes the metric and uses a nested split; that is an extension.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 11661 bytes; SHA-256 `6f917ce7dc6e2f4f266eca1e8529d6c87b16d412490f60a0a668a644959e7973`.
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
