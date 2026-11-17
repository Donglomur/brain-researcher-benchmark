# Spike inference from calcium imaging data acquired with GCaMP8 indicators

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-047`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Separate paper outcomes

The current definition supports two independent outcomes: recreate the original findings and exceed them on the same task. Each uses matched paper+data and paper+data+author-code conditions. Contract eligibility and declared protocol availability do not establish a delivered runtime or scientific result.

- [Original-finding reproduction contract](reproduction.v2.json)
- [Paired outcome protocols](outcomes.v1.json)
- [Preserved definition before dual outcomes](historical/task.pre-outcomes.v1.json)

| Outcome | Information condition | Endpoint eligibility | Protocol status | Declared availability | Scientific outcome |
| --- | --- | --- | --- | --- | --- |
| Reproduction | Paper data | source\_unresolved | unresolved | unresolved | Unknown |
| Reproduction | Paper data author code | source\_unresolved | unresolved | unresolved | Unknown |
| Improvement | Paper data | source\_unresolved | unresolved | unresolved | Unknown |
| Improvement | Paper data author code | source\_unresolved | unresolved | unresolved | Unknown |

Author-baseline replay and historical reconstruction attempts retain their original scopes. They are not promoted to qualified AI reproductions or improvements by these contracts.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. Spike inference has ordered ground-truth metrics, but the original Figure1 cohort/score and excluded-neuron author models are not recovered for the registered117-file panel. Smoothing/timing and paper-era versus corrected software differ. No numeric paper baseline or same-task win can be inferred from the released-panel controller or a generic pretrained CASCADE checkpoint.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 332240 bytes; SHA-256 `72c6089d960b0f4377349182c5d5f23e5f972f0b7177ec601806e6e4f9c0fa6a`.
- [Preserved legacy runtime declaration](implementations/registered-runtime/manifest.json)
- [Legacy declaration package](implementations/registered-runtime)

This preserved declaration is lineage, not current execution qualification. Its historical paths may describe the source snapshot.

## Task documentation

- [Source recovery notes](docs/transitive-recovery.md)

## Implementation artifacts

- [Registered runtime](implementations/registered-runtime) — Calibration only.
  Scope: This is the source package currently selected by the published catalog; current does not assert executable/scientific qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Author rate metrics v1](implementations/author-rate-metrics-v1) — Reviewed source component.
  Scope: Prepared-rate scorer for the author demo metrics. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/HelmchenLabSoftware/Cascade)
- [Code](https://github.com/PTRRupprecht/CascadeTorch)
- [Code](https://raw.githubusercontent.com/HelmchenLabSoftware/Cascade/1f9f98bf93b9b554ab68d6304aa365ab7c7ee34f/LICENSE)
- [Code](https://raw.githubusercontent.com/HelmchenLabSoftware/Cascade/1f9f98bf93b9b554ab68d6304aa365ab7c7ee34f/README.md)
- [Code](https://www.nature.com/articles/s41592-026-03183-x)
- [Code](https://www.nature.com/articles/s41592-026-03183-x.pdf)
- [Paper](https://www.nature.com/articles/s41592-026-03183-x)
- [Source](https://github.com/HelmchenLabSoftware/Cascade/tree/1f9f98bf93b9b554ab68d6304aa365ab7c7ee34f/Ground_truth)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
