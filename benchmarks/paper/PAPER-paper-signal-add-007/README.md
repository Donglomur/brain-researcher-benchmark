# Modelling neural coding in the auditory midbrain with high resolution and accuracy

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-signal-add-007`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Design ready
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
| Improvement | Paper data | design\_ready | unresolved | unresolved | Unknown |
| Improvement | Paper data author code | design\_ready | unresolved | unresolved | Unknown |

Author-baseline replay and historical reconstruction attempts retain their original scopes. They are not promoted to qualified AI reproductions or improvements by these contracts.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** design\_ready. The original Fig. 4b,d prediction task, public evaluation dataset, metric equations and reported per-sound values are recoverable. Exact masking/aggregation, baseline execution and development-data access are incomplete; the historical held-sound improvement program changes the source split and cannot produce the requested paper win.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 16819 bytes; SHA-256 `72152c0af0f167e3ed8ed83c76b37a681eb7c4b838d9ba7697f6ecc04790c0a4`.
- [Preserved legacy runtime declaration](implementations/registered-runtime/manifest.json)
- [Legacy declaration package](implementations/registered-runtime)

This preserved declaration is lineage, not current execution qualification. Its historical paths may describe the source snapshot.

## Implementation artifacts

- [Registered runtime](implementations/registered-runtime) — Calibration only.
  Scope: This is the source package currently selected by the published catalog; current does not assert executable/scientific qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Original inputs v1](implementations/original-inputs-v1) — Reviewed source component.
  Scope: Original four-sound/two-trial MAT input and probability-to-count bridge retains the authenticated 3476-unit CF mask and existing equations 3–5 scorer. Complete source files were authenticated separately; authentic numerical preparation, sound/context alignment, author inference, reference competence and protected paper-condition execution remain unestablished.
- [Probability custody v1](implementations/probability-custody-v1) — Reviewed source component.
  Scope: Additive raw categorical probability custody and verification for the complete original ICNet topology, preserving emitted float32/float64 values before the unchanged converter normalizes or derives counts. Replays the unchanged converter and grader/source equations without a second predictor pass. Fourteen accepted generated controls use all 56 streams with tiny two-bin geometry; they do not establish authentic data/model execution, full native resource adequacy, checkpoint competence, protected paper-condition reproduction/improvement, superiority or benchmark readiness. Existing v1 source artifacts, task/contracts, registered runtime and historical evidence remain unchanged.
- [Source equations v1](implementations/source-equations-v1) — Reviewed source component.
  Scope: ICNet original Fig. 4 source-equation scorer. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/fotisdr/ICNet)
- [Paper](https://www.nature.com/articles/s42256-025-01104-9)
- [Source](https://zenodo.org/records/12636772)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
