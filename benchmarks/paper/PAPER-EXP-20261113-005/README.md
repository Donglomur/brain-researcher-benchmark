# A prefrontal cortex map based on single-neuron activity

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-EXP-20261113-005`
- **Track:** Paper research
- **Registration:** Expansion draft
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. Source-native rebinding can use the original ordered SOM reconstruction endpoint in Extended Data Figure2c,d: lower quantization error means better representation of the original unit feature vectors. Exact published region-wise errors, source map capacity/topology and complete source-to-unit joins remain unrecovered. Figure4 enrichment and hierarchy findings remain descriptive calibration; the local held-animal energy-score task is a different task.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 11851 bytes; SHA-256 `f26646cd7d0dfa5a692435cf824dcb7f8232f0bf480fa2128bcd72db4787d583`.
- [Registration and provenance](../../../docs/provenance/registrations/expansion-20261113/registry.json)

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Implementation artifacts

- [Pfc clean runtime source v1](implementations/pfc-clean-runtime-source-v1) — Calibration only.
  Scope: Task association is established by the exact published paper/repository/archive join, not a folder-name inference. This is the Full99 conditional-reconstruction profile and its runtime source, not proof that the broader registered scientific contract is fulfilled. Do not associate it with PAPER-ROOT-ADD-007, which is a different PFC programme. Preserve the two sibling package names and their relative links. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Pfc conditional portable profile v1](implementations/pfc-conditional-portable-profile-v1) — Calibration only.
  Scope: Task association is established by the exact published paper/repository/archive join, not a folder-name inference. This is the Full99 conditional-reconstruction profile and its runtime source, not proof that the broader registered scientific contract is fulfilled. Do not associate it with PAPER-ROOT-ADD-007, which is a different PFC programme. Preserve the two sibling package names and their relative links. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Conditional null](implementations/conditional-null) — Calibration only.
  Scope: PFC-map paper/source family, not ROOT-ADD-007. Fixed supplied map and conditional moments are not learned-map refitting or the canonical training-only predictive primary. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Independent analytical baseline](implementations/independent-analytical-baseline) — Calibration only.
  Scope: PFC-map paper/source family, not ROOT-ADD-007. Fixed supplied map and conditional moments are not learned-map refitting or the canonical training-only predictive primary. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Matched offline harbor](implementations/matched-offline-harbor) — Calibration only.
  Scope: PFC-map paper/source family, not ROOT-ADD-007. Fixed supplied map and conditional moments are not learned-map refitting or the canonical training-only predictive primary. Offline access profile retains its explicit dependency on the Science2 source package; repair relative sibling locators and new live pins together. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Science2 package](implementations/science2-package) — Calibration only.
  Scope: PFC-map paper/source family, not ROOT-ADD-007. Fixed supplied map and conditional moments are not learned-map refitting or the canonical training-only predictive primary. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/hejDMC/pfcmap)
- [Code](https://zenodo.org/records/17559037)
- [Data](https://dandiarchive.org/dandiset/000473/)
- [Data](https://dandiarchive.org/dandiset/001260/)
- [Data](https://zenodo.org/records/17559037)
- [Paper](https://www.nature.com/articles/s41593-025-02190-z)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
