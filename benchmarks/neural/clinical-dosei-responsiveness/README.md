# Observed bedside responsiveness from causal pre-assessment EEG

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `clinical-dosei-responsiveness`
- **Track:** Neural-data understanding
- **Registration:** Expansion draft
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

Released ordered MOAAS categories 1,2,3,4,5, with source-reported merging of original 0/1 and 5/6; missing/ambiguous ratings stay null.

**Source delivery:** partial\_delivery. Exact ordinal primary/paired artifact scoring and secondary ordinal metrics exist. Source person/assessment joins, causal EEG packets, trained physiological comparators and participant execution remain unqualified.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_delivered | Complete 7,500 value causal two-channel EEG or an explicitly matched waveform rendering. No execution; exact full observation and mask/capacity policy required. | Complete authentic packet and no-tools transport. |
| Typed viewer | not\_delivered | Potential calibrated two-channel 30 second waveform display with typed time/scale actions. No clinical timestamps/labels or dose overlays; cannot silently crop to salient segments. | Restricted viewer and response-capture implementation. |
| Tool assisted | not\_delivered | Same pre-assessment waveform plus causal spectral/entropy tools. No centered/future-aware features; train-only fitted tools and fixed case budget. | Audited physiological tools and protected input path. |
| Frozen program | not\_delivered | Precommitted ordinal predictor with fixed train-only fitting recipe. Group all recordings per person; scorer schema does not enforce fit custody. | Frozen execution lifecycle and authentic baseline. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 27617 bytes; SHA-256 `a3a94564277fda5dff8a8951cfb97bbb83b11b4f05f54ff3d08e5c6cf6737502`.
- [Registration and provenance](../../../docs/provenance/registrations/expansion-20261114-v11/registry.json)

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Secondary ordinal metrics and paired participant uncertainty](docs/ordinal-metrics-v2.md)

## Implementation artifacts

- [Ordinal and paired](implementations/ordinal-and-paired) — Ordinal and paired.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification.
- [Ordinal metrics v2](implementations/ordinal-metrics-v2) — Task implementation.
  Scope: Conditional secondary ordinal reports and original-arm paired participant intervals under explicit prospective policy. Exact unchanged primary dependency; no authentic inputs, competent reference, protected execution, clinical validity or scientific qualification.
- [Participant prior v1](implementations/participant-prior-v1) — Reviewed source component.
  Scope: Participant-weighted ordinal training prior. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

No public HTTP(S) citation was extracted for this catalog entry. Consult the authoritative specification and its provenance.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
