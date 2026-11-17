# osl-dynamics, a toolbox for modeling fast dynamic brain activity

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-signal-add-004`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. The source orders fits within fixed models and representations and reports best of 10 reproducibility. Exact numeric baseline and historical objective/selection are not recovered: HMM free energy and DyNeMo final sampled training loss require different provenance. Age-effect significance and map similarity are not paper-win metrics; the held-person likelihood extension changes the original task.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 19983 bytes; SHA-256 `31dae808a16d003f6ee63a3e9bffe040480235ed350b85697feb10956b594b60`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Implementation artifacts

- [Latent state programme](implementations/latent-state-programme) — Calibration only.
  Scope: Keep mixed current/source-predecessor/context members together; this map does not select a new operative version or qualify execution. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Delivery](contracts/delivery) — Calibration only.
  Scope: Keep mixed current/source-predecessor/context members together; this map does not select a new operative version or qualify execution. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/OHBA-analysis/osl-dynamics)
- [Paper](https://elifesciences.org/articles/91949)
- [Source](https://osf.io/download/7qv9r/)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
