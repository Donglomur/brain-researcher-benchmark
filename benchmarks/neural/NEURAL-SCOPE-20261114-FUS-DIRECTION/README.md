# Calibrated target-direction inference from complete memory-period functional-ultrasound response fields

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-SCOPE-20261114-FUS-DIRECTION`
- **Track:** Neural-data understanding
- **Registration:** Expansion draft
- **Declared specification status:** Registered construction draft
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 40630 bytes; SHA-256 `115934ec062e5760e2fabc5f46faa6adc789076dad77fab99a3e79c36ef7fe6d`.
- [Registration and provenance](../../../docs/provenance/registrations/expansion-20261114/registry.json)

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Complete-field nine-map packet delivery](docs/fullfield-delivery-v1.md)

## Implementation artifacts

- [Neuroscience components](../../shared/neuroscience-components) — Mixed component collection.
  Scope: Owner IDs are a verified subset, not an exhaustive collection-to-task mapping. Preserve all child components together pending per-child ownership refinement. No association is inferred from child folder names.
- [Direction scorer](implementations/direction-scorer) — Direction scorer.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification.
- [Fullfield preparation](implementations/fullfield-preparation) — Fullfield preparation.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification.
- [Fullfield delivery v1](implementations/fullfield-delivery-v1) — Task implementation.
  Scope: Complete held-record fold delivery as lossless common-evidence packets, each containing eight calibration maps and one query map; the complete assay still requires all 48 positive folds. Native MAT normalization, authentic clocks, Run99 lineage, geometry, matched references, provider fidelity and protected scientific execution remain unqualified.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

No public HTTP(S) citation was extracted for this catalog entry. Consult the authoritative specification and its provenance.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
