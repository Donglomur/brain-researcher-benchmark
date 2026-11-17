# Reproduce held-neuron prediction in a two-area visual cortical dynamics model

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-CANDIDATE-20261114-CONSENSUS`
- **Track:** Paper research
- **Registration:** Expansion draft
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. Figure 2b supplies an ordered held-neuron prediction task, but its numeric baseline and exact historical execution are unresolved. The local source correction and trial-occurrence adapter do not establish native target isolation or paper parity. Changing to a new blocked split or a training-only PSTH is an extension, not victory over Figure 2b.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 9954 bytes; SHA-256 `75453afa9e267397e4987b48255386261fa2efc1b90fef3115b64bbc4acbfb88`.
- [Registration and provenance](../../../docs/provenance/registrations/expansion-20261114/registry.json)

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Implementation artifacts

- [Held neuron](implementations/held-neuron) — Calibration only.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Trial occurrences](implementations/trial-occurrences) — Calibration only.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Heldout row alignment](implementations/heldout-row-alignment) — Reviewed source component.
  Scope: Heldout cache row alignment. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/marineschimel/v1lm_nn)
- [Data](https://api.figshare.com/v2/articles/30983044/versions/1)
- [Data](https://doi.org/10.6084/m9.figshare.30983044.v1)
- [Data](https://doi.org/10.6084/m9.figshare.31142140)
- [Paper](https://www.nature.com/articles/s41593-026-02437-3)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
