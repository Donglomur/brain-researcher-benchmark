# MINT: A toolbox for the analysis of multivariate neural information coding and transmission

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-012`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Success:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule.

**Disposition:** source\_unresolved. MINT contains original ordered synthetic-estimator and held-out population-decoder comparisons, so the paper is not categorically ineligible. The current CA1 direct-information reference is descriptive calibration only. The exact original improvement branch, numeric author baseline, binning and fold correspondence must be recovered before admission; larger empirical direct MI or stronger significance cannot substitute for that recovery.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition (calibration only)](historical/task.pre-improvement.v1.json)

Existing reproduction graders and pilot scores remain calibration evidence. They cannot establish paper improvement. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 37805 bytes; SHA-256 `b94cddab58e870567cc2b23c58a0fa02051c9c40cc64b2e3260d8b3948ad8ae2`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Complete prepared-session fixed-bin CA1 neuron-pair mutual information, finite-sample quadratic extrapolation, IID-shuffle and temporal-shift diagnostics, animal-balanced descriptives and an explicit MAT preparation path. Authentic supplement bytes/schema and identities, spatial-bin conflict, native MINT/source-wrapper repair parity, complete empirical population, frozen reference/tolerances, protected assessment and scientific qualification remain held. PID, population decoding, other datasets and whole-paper reproduction are outside this component. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

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
