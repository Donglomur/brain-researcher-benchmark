# Predicting longitudinal state-selective calcium activity across identified neurons

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-SCOPE-20261114-HYPOTHALAMIC-DRIFT`
- **Track:** Neural-data understanding
- **Registration:** Expansion draft
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

For each neuron and wake/NREM/REM state in sessions 10–21, log1p(60×event\_count/valid\_stable\_seconds), defined only with at least 20 seconds qualified stable-state exposure.

**Source delivery:** partial\_delivery. The fixed-origin event-rate scoring equation is implemented over the complete declared cohort. Authentic event/mask production, MCH thresholds and longitudinal identities are not, so neither published preference-label figures nor a full-shaped generated forecast establish a measured forecast result.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_delivered | Potential direct numerical trajectory forecast from first 9 sessions and same state/context information. Would require explicit complete case serialization; a table of already computed targets cannot stand in for neural observation. | Bounded complete neural-history packet and no-tools response interface. |
| Typed viewer | not\_delivered | A longitudinal trace/state viewer could support inspection without changing the forecast target. Must stop at fixed origin and avoid future-normalized visualizations or all-session target panels. | Typed restricted history-only views and response collection. |
| Tool assisted | not\_delivered | Per-held-mouse numerical modelling of first 9-session histories. No target refresh; same calibrated history and training provenance as programme comparator. | Candidate episode interface; scorer alone does not deliver investigative tools. |
| Frozen program | not\_delivered | Precommitted open-loop programme produces 36 future values per neuron. Fit/adapt only on declared training mice and held first 9 sessions, freeze all future forecasts together. | Source input/target producers, programme runner and competent fitted references. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

**Specification alias:** This registered ID refers to specification HOLD-NEURAL-FRONTIER-HYPODRIFT-20261114; the alias does not establish another independent study or dataset.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 27174 bytes; SHA-256 `bebe7e67c0fdb100746dc9a5169f1422fe4cd72f360274d5b7b36859b4645de9`.
- [Registration and provenance](../../../docs/provenance/registrations/expansion-20261114/registry.json)

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Implementation artifacts

- [Fixed origin forecast](implementations/fixed-origin-forecast) — Fixed origin forecast.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification.
- [Fixed origin delivery v1](implementations/fixed-origin-delivery-v1) — Reviewed source component.
  Scope: Fixed-origin event-history delivery. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://doi.org/10.5281/zenodo.20747988)
- [Code](https://github.com/ZENLabCode/CalciumImaging)
- [Paper](https://www.nature.com/articles/s41467-026-75792-1)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
