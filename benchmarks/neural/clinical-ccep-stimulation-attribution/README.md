# Anatomical stimulation-site attribution from complete VTC evoked responses

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `clinical-ccep-stimulation-attribution`
- **Track:** Neural-data understanding
- **Registration:** Expansion draft
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

Authenticated stimulation-pair anatomy in the frozen four-compartment order hippocampus, amygdala, lateral\_temporal\_cortex, other\_mixed.

**Source delivery:** partial\_delivery. Five-patient primary prediction-artifact scorer and complete-block pairing/metadata components exist; authentic waveform-to-anatomy joins, full participant packets, fitted references and protected runner remain missing.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_delivered | Proposed complete all-repetition VTC waveform matrix or lossless plots. No tools; full packet must fit before declaring direct evidence. | Authenticated input packet and capacity protocol. |
| Typed viewer | not\_delivered | Potential repetition-aware waveform display with typed channel/time/repetition views. No anatomy/event lookup, target-bearing titles or raw-owner data. | Viewer implementation and rendering/response audit. |
| Tool assisted | not\_delivered | Proposed same matrix plus train-only templates/numerical analysis. Case-fresh tool state and identical training evidence, no test BPC fitting. | Protected tool runner and competent train-only template model. |
| Frozen program | not\_delivered | Proposed precommitted waveform/template classifier. Freeze fitting policy on training patients; artifact scoring alone is not program execution. | Frozen lifecycle and authentic reference qualification. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 28108 bytes; SHA-256 `a7d3c3cf096078d68ee6047d4b6e55af6f1ba225ced38530bbb2a1bb343c4a40`.
- [Registration and provenance](../../../docs/provenance/registrations/expansion-20261114-v11/registry.json)

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Current metadata validation command](docs/current-metadata-cli.md)

## Implementation artifacts

- [Clinical ccep artifact grading](implementations/clinical-ccep-artifact-grading) — Task implementation source.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification.
- [Clinical ccep native metadata](implementations/clinical-ccep-native-metadata) — Task implementation source.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification.
- [Clinical ccep pairing](implementations/clinical-ccep-pairing) — Task implementation source.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification.
- [Clinical ccep coordinate binding](implementations/clinical-ccep-coordinate-binding) — Reviewed source component.
  Scope: Reviewed additive source component for the existing task. The package documentation and source contracts define its scope; source enrollment does not establish authentic-data execution or scientific qualification.
- [Complete observation v1](implementations/complete-observation-v1) — Reviewed source component.
  Scope: Complete supplied normalized VTC observation delivery and strict probability response collection preserve current scorer format, including cases without permissible null pairing. Authentic conversion, event/contact joins, rights, native units and protected scientific execution remain unqualified.
- [Training prevalence v1](implementations/training-prevalence-v1) — Reviewed source component.
  Scope: Frozen training-prevalence reference. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

No public HTTP(S) citation was extracted for this catalog entry. Consult the authoritative specification and its provenance.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
