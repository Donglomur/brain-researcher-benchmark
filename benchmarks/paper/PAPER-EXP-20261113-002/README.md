# Flexible neural population dynamics govern the speed and stability of sensory encoding in mouse visual cortex

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-EXP-20261113-002`
- **Track:** Paper research
- **Registration:** Expansion draft
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. The original six-speed decoding task is ordered, but complete Figure 2h/4d,e accuracy matrices, original split realizations and exact figure-producing settings are not recovered. The source correctly uses different within-time and cross-time CV protocols. The existing chronological pooled-state protocol changes source splits and input permissions and remains an extension.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 9420 bytes; SHA-256 `5c131b9c18b1f71aced93995dfc64ea8cec68d9316e568be0a34d71ac6cf7e0e`.
- [Registration and provenance](../../../docs/provenance/registrations/expansion-20261113/registry.json)

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Implementation artifacts

- [Frozen decoder](implementations/frozen-decoder) — Calibration only.
  Scope: Package README scientific-context citation/title matches this registered expansion specification; preserve closed six-file helper package. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://doi.org/10.5281/zenodo.12801956)
- [Code](https://github.com/eabhorrocks/Horrocksetal24_TemporalDynamics)
- [Data](https://doi.org/10.6084/m9.figshare.26031226.v1)
- [Paper](https://www.nature.com/articles/s41467-024-50563-y)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
