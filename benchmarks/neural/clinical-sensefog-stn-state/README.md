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

**Source delivery:** partial\_delivery. Complete recording-grid lag-map source exists, but no primary gait-state scorer, authentic labels/signal packets or candidate runner is delivered. Target-free lag controls alone do not measure neural understanding.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_delivered | Proposed complete all-channel 2 secondLFP numeric/waveform case. No tools and no movement/annotation context; full montage must be retained. | Authenticated signal packets, answer schema and no-tools transport. |
| Typed viewer | not\_delivered | Potential calibrated bilateral LFP trace/spectrum display. Typed action policy cannot expose state-labelled IMU/EMG or event overlays. | Viewer implementation and protected capture. |
| Tool assisted | not\_delivered | Proposed same LFP with causal spectral/model tools. Fixed per-case evidence/compute; models fitted only in other 11 people. | Full participant inputs, scorer and qualified frozen decoder. |
| Frozen program | not\_delivered | Proposed precommitted gait-state probability program. Freeze causal lookback and training recipe; mapper does not execute or grade predictions. | Primary scorer and frozen lifecycle. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 30289 bytes; SHA-256 `4ed035ea7c136d7ae06fd4b1d3ace4db071ded67a002d0385df99db9850283b2`.
- [Registration and provenance](../../../docs/provenance/registrations/expansion-20261114-v11/registry.json)

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Implementation artifacts

- [Recording lag controls](implementations/recording-lag-controls) — Recording lag controls.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

No public HTTP(S) citation was extracted for this catalog entry. Consult the authoritative specification and its provenance.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
