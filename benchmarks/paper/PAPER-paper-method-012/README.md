# MINT: A toolbox for the analysis of multivariate neural information coding and transmission

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-012`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Separate paper outcomes

The current definition supports two independent outcomes: recreate the original findings and exceed them on the same task. Each uses matched paper+data and paper+data+author-code conditions. Contract eligibility and declared protocol availability do not establish a delivered runtime or scientific result.

### Current selected paper endpoint

**Disposition:** source\_unresolved.

This version selects an exact author-reported computational result as the primary benchmark endpoint. The broader biological finding and prior contracts retain their original scope. The source selection does not establish runnable delivery, an AI evaluation, reproduction or improvement; both access conditions remain uninstantiated.

- [Selected current improvement contract](primary-endpoint-v1/improvement.v1.json)
- [Authenticated endpoint selection](primary-endpoint-v1/selection.v1.json)
- [Reviewed endpoint selection authority](../../../docs/provenance/paper-primary-endpoint-selections.v2.json)

**Remaining reproduction/source limits:**

- Authenticate S1 payload and original animal/session/response/stimulus membership and spatial-bin conventions.
- Resolve fivefold paper versus twofold source and exact nested optimization/outer trial partitions.
- Resolve swapped shuffled-linear/RBF assignments and caption stimulus-column inconsistency; direct-MI commented call must not silently supply decoder outputs.
- Recover native confusion counts, all session/fold outputs and exact original aggregate/reference vectors.
- Qualify source-matched reproduction tolerance, strongest comparator selection, meaningful gain and dependence-aware joint decision; budgets and independent execution remain unqualified.

- [Selected-endpoint reproduction contract](primary-endpoint-v1/reproduction.v2.json)
- [Paired outcome protocols](primary-endpoint-v1/outcomes.v1.json)
- [Preserved definition before dual outcomes](historical/task.pre-outcomes.v1.json)

| Outcome | Information condition | Endpoint eligibility | Protocol status | Declared availability | Scientific outcome |
| --- | --- | --- | --- | --- | --- |
| Reproduction | Paper data | source\_unresolved | unresolved | unresolved | Unknown |
| Reproduction | Paper data author code | source\_unresolved | unresolved | unresolved | Unknown |
| Improvement | Paper data | source\_unresolved | unresolved | unresolved | Unknown |
| Improvement | Paper data author code | source\_unresolved | unresolved | unresolved | Unknown |

Author-baseline replay and historical reconstruction attempts retain their original scopes. They are not promoted to qualified AI reproductions or improvements by these contracts.

## Retained predecessor improvement policy

This original contract preserves the predecessor scientific instructions and source scope. The selected primary policy above governs current improvement.

**Disposition:** source\_unresolved. MINT contains original ordered synthetic-estimator and held-out population-decoder comparisons, so the paper is not categorically ineligible. The current CA1 direct-information reference is descriptive calibration only. The exact original improvement branch, numeric author baseline, binning and fold correspondence must be recovered before admission; larger empirical direct MI or stronger significance cannot substitute for that recovery.

- [Retained original improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 41909 bytes; SHA-256 `b69c8d25ccb63216a00fee480aa4770f5ecc51d376fa43d98ac7725e13af330c`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Complete prepared-session fixed-bin CA1 neuron-pair mutual information, finite-sample quadratic extrapolation, IID-shuffle and temporal-shift diagnostics, animal-balanced descriptives and an explicit MAT preparation path. Authentic supplement bytes/schema and identities, spatial-bin conflict, native MINT/source-wrapper repair parity, complete empirical population, frozen reference/tolerances, protected assessment and scientific qualification remain held. PID, population decoding, other datasets and whole-paper reproduction are outside this component. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Poisson truth v1](implementations/poisson-truth-v1) — Reviewed source component.
  Scope: MINT original Poisson-process information reference. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/panzerilab/MINT)
- [Code](https://github.com/panzerilab/MINT/blob/f0d43b68a6e8541f56b3ca67d9af5a7a0e76acbb/BuildMINT.m)
- [Code](https://github.com/panzerilab/MINT/blob/f0d43b68a6e8541f56b3ca67d9af5a7a0e76acbb/How_to_use_MINT/How_to_compute_MI.m)
- [Code](https://github.com/panzerilab/MINT/blob/f0d43b68a6e8541f56b3ca67d9af5a7a0e76acbb/How_to_use_MINT/How_to_compute_non_discrete.m)
- [Code](https://raw.githubusercontent.com/panzerilab/MINT/f0d43b68a6e8541f56b3ca67d9af5a7a0e76acbb/README.md)
- [Code](https://zenodo.org/records/13998526)
- [Source](https://doi.org/10.1371/journal.pcbi.1012934.s002)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
