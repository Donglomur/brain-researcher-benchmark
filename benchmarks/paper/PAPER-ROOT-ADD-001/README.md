# Mapping the neuronal building blocks of human language with language models

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-ROOT-ADD-001`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Design ready
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** design\_ready. The original contextual model-to-neuron prediction task has an ordered score and a published Figure 3b mean of 0.05, supporting a design rather than an admitted win condition. Exact figure reduction, unrounded baseline and complete source cohort/panel mapping remain open. Neither native artifact MAE nor a new purged-sentence interface can establish improvement; selecting only a narrower population panel would not fulfill the complete intended task.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 21301 bytes; SHA-256 `830df89d0b6c2e206db15b9025f357f942b6084fcd13008d583dd5ef1b066f42`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Implementation artifacts

- [Language programme](implementations/language-programme) — Calibration only.
  Scope: Keep mixed current/source-predecessor/context members together; this map does not select a new operative version or qualify execution. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Delivery source](implementations/delivery-source) — Calibration only.
  Scope: Keep mixed current/source-predecessor/context members together; this map does not select a new operative version or qualify execution. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Original figure3 v1](implementations/original-figure3-v1) — Reviewed source component.
  Scope: Original Figure 3 output reduction. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://zenodo.org/records/20128462)
- [Paper](https://www.nature.com/articles/s41586-026-10691-5)
- [Source](https://zenodo.org/records/20128462)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
