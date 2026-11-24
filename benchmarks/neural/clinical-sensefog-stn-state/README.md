# Participant-held gait-state inference from bilateral STN LFP

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `clinical-sensefog-stn-state`
- **Track:** Neural-data understanding
- **Registration:** Expansion draft
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

Original behavioral/clinical interval annotations for freezing, voluntary stop, continuous walking, sitting and standing, subject to authentic dictionary and boundary validation.

**Source delivery:** partial\_delivery. Complete recording-grid lag-map source and protected primary probability/paired lag-loss scoring source exist. Authenticated clinical labels and signal packets, qualified decoders and protected candidate execution remain unestablished; source availability alone does not measure neural understanding.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_delivered | Proposed complete all-channel 2 secondLFP numeric/waveform case. No tools and no movement/annotation context; full montage must be retained. | Authenticated signal packets, answer schema and no-tools transport. |
| Typed viewer | not\_delivered | Potential calibrated bilateral LFP trace/spectrum display. Typed action policy cannot expose state-labelled IMU/EMG or event overlays. | Viewer implementation and protected capture. |
| Tool assisted | not\_delivered | Proposed same LFP with causal spectral/model tools. Fixed per-case evidence/compute; models fitted only in other 11 people. | Authenticated full participant inputs, protected tool execution, equal-information transport and a qualified frozen decoder. |
| Frozen program | not\_delivered | Proposed precommitted gait-state probability program. Freeze causal lookback and training recipe; the protected scorer can grade supplied probabilities, but does not execute or authenticate the frozen programme lifecycle. | Authenticated full participant inputs, qualified reference models and a protected frozen programme lifecycle. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 30893 bytes; SHA-256 `07a8dffbc95aaaa183030cab23f53bdec3dc0a2c497188175fd508f52a1f52ff`.
- [Registration and provenance](../../../docs/provenance/registrations/expansion-20261114-v11/registry.json)

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Implementation artifacts

- [Participant delivery v1](implementations/participant-delivery-v1) — Reviewed source component.
  Scope: In-memory opaque probability requests and strict response collection connect supplied bilateral STN waveform projection to protected participant-macro scoring. It is not a network runner, sandbox, source-authentication mechanism or evidence of matched participant access.
- [Signal packets v1](implementations/signal-packets-v1) — Reviewed source component.
  Scope: Reviewed additive source component for the existing task. The package documentation and source contracts define its scope; source enrollment does not establish authentic-data execution or scientific qualification.
- [Recording lag controls](implementations/recording-lag-controls) — Recording lag controls.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification.
- [Primary scoring v1](implementations/primary-scoring-v1) — Reviewed source component.
  Scope: SenseFOG protected probability scoring. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

No public HTTP(S) citation was extracted for this catalog entry. Consult the authoritative specification and its provenance.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
