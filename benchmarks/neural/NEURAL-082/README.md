# Rhythm versus melody information in music imagery

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-082`
- **Track:** Neural-data understanding
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

A signed held-out identity-loss contrast on a source-verified matched excerpt set; an inconclusive or unavailable contrast is valid if support is insufficient.

**Source delivery:** target\_mismatch. The registered OpenMIIR rhythm-versus-melody question lacks verified matched support and a delivered scorer. Its only runtime manifest instead describes unscored 21-person music/score identity and explicitly disclaims revival of the original question.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_delivered | Potential imagery waveform observation with a fixed matched-excerpt answer set; no actual case packet exists. Do not expose excerpt-coded cues or use alternate score-guided data under the original target. | Validated matched set, authentic case packet and no-tools response path. |
| Typed viewer | not\_delivered | Potential controlled EEG waveform viewer for a verified matched task. Viewing scores or target-defining metadata would change the observation contract; no implementation exists. | Typed viewer, source-bound response schema and transport. |
| Tool assisted | not\_delivered | Proposed matched-set investigation of EEG information beyond rhythm/cue/time. A per-case analysis cannot obtain original ground truth from the unrelated programme manifest or source-paper conclusion. | Original source match support, numerical evaluator and isolated investigation path. |
| Frozen program | not\_delivered | Only an unscored alternate 21-person programme is declared; original OpenMIIR executable/scorer closure is absent. Source/fit/seal declaration does not make the different music/score target equivalent or runtime-qualified. | Original-target programme and complete authentic scoring path. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 15767 bytes; SHA-256 `118b2baf716ee2b5286c9dce34969543cc8de549cee7e67415a1a56efdfd4732`.
- [Preserved legacy runtime declaration](implementations/registered-runtime/manifest.json)
- [Legacy declaration package](implementations/registered-runtime)

This preserved declaration is lineage, not current execution qualification. Its historical paths may describe the source snapshot.

## Implementation artifacts

- [Registered runtime](implementations/registered-runtime) — Catalog registered source package.
  Scope: This is the source package currently selected by the published catalog; current does not assert executable/scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Source](https://github.com/sstober/openmiir)
- [Source](https://openmiir.github.io/)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
