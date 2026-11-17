# Continuous self-motion reconstruction from simultaneous vestibular spike trains

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-DISC-20261114-VESTIBULAR-VO`
- **Track:** Neural-data understanding
- **Registration:** Expansion draft
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

Measured angular head velocity at every valid native target sample of a complete held stimulus repeat. Reconstructing this measured trajectory is a neural decoding target; reproducing the paper’s encoding/correlation figures is not the answer.

**Source delivery:** partial\_delivery. The animal-by-condition velocity scorer is implemented for complete normalized prediction artifacts. No authentic MATLAB loader, neural packet, trained comparator producer or participant execution route is delivered; first reconcile actual pair/repeat clocks and the training-only phase prior.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_delivered | Proposed fixed numeric spike-raster/count observations over complete repeat cores, with timebase and declared history. No numerical/model tools; preserve all samples via fixed tiling and score each core once. Derived rate displays would be separately identified substrates. | Complete authentic direct packet and response transport; feasibility of full-duration numeric output not established. |
| Typed viewer | not\_delivered | Potential typed raster/time-axis display of the same spike observations. Restricted render/zoom/pan actions may reveal only declared input support, never velocity, waveform identity or hidden phase. | No typed viewer, image transport or full-coverage response collector exists for this task. |
| Tool assisted | not\_delivered | Numerical per-case decoder investigation on identical spike packets and calibration. Equal input/checkpoint/tool/compute budget, no target feedback; reset case state as declared. The scorer accepts a case\_investigation artifact label only. | No authenticated input or case-adaptive participant runner; label does not prove execution. |
| Frozen program | not\_delivered | Precommitted spike-to-velocity programme and train-only fit/adaptation recipe. Freeze code, preprocessing, lags and calibration before held-repeat access; scorer accepts completed arrays but never runs the producer. | Complete programme training/inference harness, budgets and authentic comparator production. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 25982 bytes; SHA-256 `ec245b059cf6dd8187360bca2d9a20fa2493bfdd5b94514fa9431ca103d1f094`.
- [Registration and provenance](../../../docs/provenance/registrations/expansion-20261114-v11/registry.json)

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Implementation artifacts

- [Condition evaluator](implementations/condition-evaluator) — Condition evaluator.
  Scope: Complete normalized animal-by-condition evaluator with equal-repeat then equal-group MSE, frozen training-only prior comparison and separate singleton diagnostics. Authentic identities, clocks, masks, prior provenance/competence and protected execution remain external requirements; no scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

No public HTTP(S) citation was extracted for this catalog entry. Consult the authoritative specification and its provenance.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
