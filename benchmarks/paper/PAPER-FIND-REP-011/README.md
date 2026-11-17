# Local and global predictors of synapse elimination during motor learning

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-FIND-REP-011`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. The paper explicitly selects mixed-effects terms using model log-likelihood, so an original evaluated fit-comparison route exists for activity/coactivity responses. Its original candidate model set, complexity constraints, likelihood definition, fitting mode, exact analysis rows and numeric results have not been recovered. This potential source-native route remains blocked; it is not predictive validation and cannot be replaced by the local elimination-fate Brier task.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 29123 bytes; SHA-256 `a4ad65cf2d3fb9c970023cb59e6f3430123a0244da3a7ff6a44d06b919c83c68`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Processed binary activity/coactivity derivation, explicit next-visit structural outcomes and fixed competing predictors fitted with leave-one-mouse-out transforms and calibration on a retrospectively adjudicated cohort. Native identity/fate conversion, complete source population, original mixed-effects/spatial/timing analyses and protected replay remain held. The endpoint is neither survival nor causal inference; scientific qualification is unknown. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://doi.org/10.5281/zenodo.10108836)
- [Paper](https://doi.org/10.1126/sciadv.adk0540)
- [Source](https://doi.org/10.5281/zenodo.10108836)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
