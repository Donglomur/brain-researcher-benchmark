# Tracking the neurodevelopmental trajectory of beta band oscillations with optically pumped magnetometer-based magnetoencephalography

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-signal-add-005`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Success:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule.

**Disposition:** source\_unresolved. Appendix2 evaluates an original ordered geometric comparison: participant sensor-to-scalp distances with actual adaptable helmets versus a virtually rigid-registered single largest helmet. This source-native comparison merits source recovery rather than blanket exclusion based on the descriptive age–beta endpoint. Exact distance vectors/head-model bindings and a physically feasible, source-comparable computational candidate domain are unresolved; no hardware redesign or free sensor placement is authorized or benchmark-ready.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition (calibration only)](historical/task.pre-improvement.v1.json)

Existing reproduction graders and pilot scores remain calibration evidence. They cannot establish paper improvement. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 24927 bytes; SHA-256 `4d41d82d681189ab1c5ece43b80b4be4661601b354ad5f8ccc8959e7550cf583`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Downstream beta-amplitude evaluation at pre-extracted source peaks, with all 53 participant dispositions and 51 included participants, code/paper normalization profiles, age/covariate models, uncertainty and matched-trial diagnostics. Native MEG preprocessing/peaks/band extraction, normalization parity, authentic cohort/covariates, event surrogates, rights and protected references remain held. Scientific qualification is unknown. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/LukasRier/RierRhodes_2024_Neurodevelopmental_OPMMEG)
- [Paper](https://elifesciences.org/articles/94561)
- [Source](https://zenodo.org/records/11126593)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
