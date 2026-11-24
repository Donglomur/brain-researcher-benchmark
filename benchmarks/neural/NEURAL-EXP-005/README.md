# Neonatal seizure-report probability from complete causal EEG windows

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-EXP-005`
- **Track:** Neural-data understanding
- **Registration:** Expansion draft
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

For every eligible second, q=(a1+a2+a3)/3 from the three aligned binary expert streams. This is an uncertain expert-report target, not a unique verified seizure truth.

**Source delivery:** partial\_delivery. The normalized evaluator implements the registered full-support soft-vote endpoint and numeric case packet. It does not parse/authenticate the 79 EDFs and corrected labels, fit competent comparators, or supply any protected participant mode.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_delivered | Possible full 30-second numeric or waveform interpretation with all channels and fixed units. Any representation must preserve scientific information and exact timing; no context-driven downsampling presumed equivalent. | No direct-model transport or validated complete waveform representation. |
| Typed viewer | not\_delivered | Potential bounded multi-channel waveform viewer for exactly the same causal packet. Typed channel/time/gain actions must stay inside the single packet; no labels/raw-array escape or neighboring-window access. | No typed-viewer implementation or isolation evidence for this task. |
| Tool assisted | not\_delivered | Per-case numerical analysis of the exact EEG packet with admitted train-only detector tools. Fresh case context, immutable training artifacts, no feedback; identical source flags and observations across comparators. | Packet API is available; participant analysis/model-tool harness and competent tool checkpoints are not delivered. |
| Frozen program | not\_delivered | Precommitted predictor and fold-specific training/calibration recipe consuming the same causal packet. Freeze before held labels; fresh process per case and no later overlapping EEG. | No frozen-program runner, qualified train-only fit or protected complete-source execution. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 20253 bytes; SHA-256 `114c494b128ed144d49cfea62a8ecf89eef4f1fead87eb3095e740f78f5d552c`.
- [Registration and provenance](../../../docs/provenance/registrations/expansion-20261113/registry.json)

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Implementation artifacts

- [Complete support evaluator](implementations/complete-support-evaluator) — Complete support evaluator.
  Scope: Complete normalized 79-infant probability endpoint, exact causal EEG packets and equal-infant Brier comparisons. Generated controls and source review do not verify authentic EDF/annotation alignment, input quality flags, reference competence, protected execution or scientific qualification.
- [Source admission v1](implementations/source-admission-v1) — Reviewed source component.
  Scope: Original 79-recording, three-rater source bridge with calibrated lazy native windows, complete quality census and the current evaluator projection on the authenticated exported record grid. Full source custody, authentic preparation, competent train-only references and protected participant transport remain open; clinical continuity and source quality flags are not inferred acquisition-pause truth.
- [Numeric program v1](implementations/numeric-program-v1) — Reviewed source component.
  Scope: Local frozen-program source consumes complete supplied causal 30-second, 18-channel EEG packets and predicts expert vote fractions with equal infant weighting. Generated controls do not authenticate source inputs, qualify a reference or establish neural understanding across the original 79 infants.
- [Raster collection v1](implementations/raster-collection-v1) — Reviewed source component.
  Scope: Reviewed additive source component for the existing task. Package source contracts define exact interfaces and limits; source enrollment does not establish authentic-data execution, native/runtime isolation, competent reference performance or scientific qualification.
- [Raster process transport v1](implementations/raster-process-transport-v1) — Reviewed source component.
  Scope: Reviewed additive source component for the existing task. Package source contracts define exact interfaces and limits; source enrollment does not establish authentic-data execution, native/runtime isolation, competent reference performance or scientific qualification.
- [Raster run entrypoint v1](implementations/raster-run-entrypoint-v1) — Reviewed source component.
  Scope: Reviewed additive source component for the existing task. Package source contracts define exact interfaces and limits; source enrollment does not establish authentic-data execution, native/runtime isolation, competent reference performance or scientific qualification.
- [Typed raster viewer v1](implementations/typed-raster-viewer-v1) — Reviewed source component.
  Scope: Reviewed additive source component for the existing task. Package source contracts define exact interfaces and limits; source enrollment does not establish authentic-data execution, native/runtime isolation, competent reference performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/ktapani/Neonatal_Seizure_Detection)
- [Code](https://github.com/ktapani/Neonatal_Seizure_Detection/tree/1a59e4b414f28aba52e61c3360fdc324199071b4)
- [Data](https://zenodo.org/records/4940267)
- [Paper](https://www.nature.com/articles/sdata201939)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
