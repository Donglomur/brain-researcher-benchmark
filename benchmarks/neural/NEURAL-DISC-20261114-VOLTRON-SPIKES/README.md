# Optical voltage trace to independently recorded spike timing across complete cell recordings

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-DISC-20261114-VOLTRON-SPIKES`
- **Track:** Neural-data understanding
- **Registration:** Expansion draft
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

Electrophysiological spike-event times at authentic electrical sample locations, adjudicated independently of optical predictions; the present repository has no complete qualified event reference.

**Source delivery:** partial\_delivery. The current six-subject native-frame event scorer is delivered as a source component. This revision adopts its explicit 12-cell/34-movie deposited scope and replaces the stale nominal-clock/seven-group assumptions. Authentic optical extraction, electrical reference events and participant access remain unqualified.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_delivered | Proposed numeric or fixed waveform-image optical trace tiles retaining complete frame cores and declared context halos. No tools and no patch channel; outputs remain native frame indices with at most one event per frame. Full-frame coverage must match programme arms. | No authentic optical trace packets, direct image/numeric transport or full response collection. |
| Typed viewer | not\_delivered | Potential typed optical trace viewer with native time axis, polarity/exposure and bounded zoom. Only optical observations; electrical labels, private validity, raw hidden channels and representation ceiling stay evaluator-only. | No typed viewer/action protocol or image delivery for this registration. |
| Tool assisted | not\_delivered | Per-movie numerical optical event analysis with fixed permitted tools/checkpoints. Same trace/calibration/halo substrate as other arms; richer-video processing is a separately labelled condition; no score feedback during held inference. | No per-case investigation runner, authentic matched packets or resource logs. |
| Frozen program | not\_delivered | Precommitted optical trace-to-frame-event programme plus train-only calibration recipe. Scorer requires programme/calibration digests and complete predictions but does not execute or verify the producer; freeze before held-subject access. | No qualified optical comparator/candidate producer or protected programme execution. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 20661 bytes; SHA-256 `7b9cf7c2e6bf4ffc1f4b6d39f7b4b0c665d4f0dde2b30415755f6f6be6915c15`.
- [Registration and provenance](../../../docs/provenance/registrations/expansion-20261114-v11/registry.json)

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Data scope](docs/data-scope.md)

## Implementation artifacts

- [Voltron complete spike events](implementations/voltron-complete-spike-events) — Task implementation source.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification.
- [Voltron native frame events v1](implementations/voltron-native-frame-events-v1) — Task implementation source.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

No public HTTP(S) citation was extracted for this catalog entry. Consult the authoritative specification and its provenance.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
