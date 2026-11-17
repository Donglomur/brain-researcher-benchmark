# Reproduce and improve context-transfer time decoding in mouse medial entorhinal cortex

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-ADMISSION-STRUCTURED-EXPERIENCE-20261113`
- **Track:** Paper research
- **Registration:** Expansion draft
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. The original ephys decoder has an ordered time-prediction error, but its numeric error baseline and a defensible original-score comparison are not recovered. Figure 6f reports a shaping-group difference, not a performance threshold. The existing leave-one-mouse-out, mouse-macro proposal changes the paper protocol and cannot establish a same-task paper win.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 13070 bytes; SHA-256 `863ac92b681738ffae5c2e6a51ad83018e758ab76c37b58211a8627826027310`.
- [Registration and provenance](../../../docs/provenance/registrations/expansion-20261114/registry.json)

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Prepares 390 source-context fit units and private expected rows for the full declared 13-session/eight-mouse roster, scores mouse-macro circular error, and separately summarizes complete 13 × 9 source-concordance tables. Authentic behavior/unit/trial support, zero-event trial resolution, paper 1 s/source 0.5 s ambiguity, file-scoped rights, native LDA parity, protected runtime isolation and all nine scientific admission gates remain open. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Original row score v1](implementations/original-row-score-v1) — Reviewed source component.
  Scope: Original ephys row scorer. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Paper](https://www.nature.com/articles/s41593-026-02409-7)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
