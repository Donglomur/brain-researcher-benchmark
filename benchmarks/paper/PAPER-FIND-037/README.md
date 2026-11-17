# The neural correlates of novelty and variability in human decision-making under an active inference framework

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-FIND-037`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. The canonical registration explicitly includes behavioral model comparison, and the source provides an ordered BIC comparison, so this is source-unresolved rather than a newly invented prediction task. Exact original BIC values, likelihood/parameter-count semantics and code-to-paper correspondence remain unresolved. EEG association strength is not an ordered paper-win endpoint.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 21638 bytes; SHA-256 `48e9390dbe19ad611285822aa67c6a548e8b9b7c842a1cab2bd3dd494ccb44c3`.
- [Preserved legacy runtime declaration](implementations/registered-runtime/manifest.json)
- [Legacy declaration package](implementations/registered-runtime)

This preserved declaration is lineage, not current execution qualification. Its historical paths may describe the source snapshot.

## Implementation artifacts

- [Registered runtime](implementations/registered-runtime) — Calibration only.
  Scope: This is the source package currently selected by the published catalog; current does not assert executable/scientific qualification. This retained scoring facade requires 2 source or input dependencies absent from the public baseline. Correcting its repository locator does not make it runnable from this checkout alone. This limit does not apply automatically to sibling implementations of the task. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Source statistic v1](implementations/source-statistic-v1) — Reviewed source component.
  Scope: Original behavioral source statistic. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/andlab-um/FreeEnergyEEG)
- [Paper](https://elifesciences.org/articles/92892)
- [Source](https://github.com/andlab-um/FreeEnergyEEG)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
