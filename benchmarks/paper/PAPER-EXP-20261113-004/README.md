# A flexible hippocampal population code for experience relative to reward

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-EXP-20261113-004`
- **Track:** Paper research
- **Registration:** Expansion draft
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Success:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule.

**Disposition:** source\_unresolved. The original Fig. 3 reward-relative decoder has an ordered score, but its exact published score vector, historical folds, cell-selection privileges and author revision are not recovered. The current chronological post-switch-calibration evaluator changes the original protocol and cannot establish a same-task paper win.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition (calibration only)](historical/task.pre-improvement.v1.json)

Existing reproduction graders and pilot scores remain calibration evidence. They cannot establish paper improvement. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 9207 bytes; SHA-256 `4d9ffa73599b9830ee9d24850881cd7ce3ca3f757eb1c0cf14709af0aa8b33bb`.
- [Registration and provenance](../../../docs/provenance/registrations/expansion-20261113/registry.json)

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Owner-side chronological calibration/guard/evaluation splitting, opaque neural-only query projection and paired animal-level cosine scoring for the prospective reward-relative improvement endpoint, with the 11-animal by seven-day structural panel. Complete Figures 2–3 reproduction, authentic coordinate and native-loader equivalence, cohort/cell admission, official calibrated comparator and occupancy shuffles, protected execution and measured native resources remain unresolved. Receipts and hashes do not authenticate actual fitting behavior. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/GiocomoLab/Sosa_et_al_2024)
- [Data](https://doi.org/10.25452/figshare.plus.27098065)
- [Data](https://doi.org/10.25452/figshare.plus.27138633)
- [Data](https://doi.org/10.48324/dandi.001361/0.250406.0045)
- [Paper](https://www.nature.com/articles/s41593-025-01985-4)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
