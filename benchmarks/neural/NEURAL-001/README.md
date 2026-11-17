# Audiobook-calibrated sentence-envelope inference from MEG

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-001`
- **Track:** Neural-data understanding
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

The source processed acoustic-envelope time series over each complete OLSA interval; this measured stimulus target is separate from the source paper’s published aggregate result.

**Source delivery:** partial\_delivery. The complete24-person/2880-interval programme recipe and scorer exist, but authenticated packets and an admitted executable environment are absent. The concrete target is unseen-sentence acoustic-envelope reconstruction after same-person audiobook calibration, not a decoder fitted without that person.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_delivered | A numerical or plotted complete sentence MEG observation could support a separate no-tools response condition. Must retain identical interval support/calibration information while preventing code, fitted decoder calls and source identity access. | No direct response renderer/collection protocol or model trial for this task. |
| Typed viewer | not\_delivered | Potential channel/time rendering of complete306-channel sentence MEG with typed navigation. Typed image-only actions would need fixed content/precision and complete response collection; current numerical tools are not this viewer. | No typed renderer or participant transport supplied. |
| Tool assisted | source\_available | Fresh per-case investigation loop with bounded numerical Python tools and a submitted inference program. Same admitted inputs/tools/compute as comparator; engine must enforce target and other-query exclusion; returned text tools are not direct observation. | Actual engine/provider/isolation qualifications and authenticated operands. |
| Frozen program | source\_available | Precommitted method with training-only calibration and declared inference procedure. Freeze source/fit rules before held observations; fresh per-person state, no query fitting or target feedback. | Runnable admission profile and complete authenticated packets; CLI currently refuses. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 16721 bytes; SHA-256 `630cd90ee3197f64ad6f8525a1611bc858b1412f39fb46d57ff7a58cee5444b4`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Implementation artifacts

- [Programme source](implementations/programme-source) — Task implementation.
  Scope: Keep mixed current/source-predecessor/context members together; this map does not select a new operative version or qualify execution.
- [Intake and delivery](implementations/intake-and-delivery) — Task implementation.
  Scope: Keep mixed current/source-predecessor/context members together; this map does not select a new operative version or qualify execution.
- [Opaque delivery v1](implementations/opaque-delivery-v1) — Reviewed source component.
  Scope: Opaque delivery projection. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Source](https://github.com/tillhabersetzer/MEG-SCANS)
- [Source](https://openneuro.org/datasets/ds006468/versions/1.1.1)
- [Source](https://raw.githubusercontent.com/tillhabersetzer/MEG-SCANS/32bfc690e28e7591b45d96615c59b2d53b6a7165/speech/decoding/training_decoding.m)
- [Source](https://s3.amazonaws.com/openneuro.org/ds006468/dataset_description.json)
- [Source](https://s3.amazonaws.com/openneuro.org/ds006468/sub-01/meg/sub-01_task-olsa_events.tsv)
- [Source](https://www.nature.com/articles/s41597-025-06397-4)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
