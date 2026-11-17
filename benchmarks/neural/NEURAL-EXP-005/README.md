# Uncertainty-aware neonatal seizure evidence from held-infant EEG

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-EXP-005`
- **Track:** Neural-data understanding
- **Registration:** Expansion draft
- **Declared specification status:** Registered construction draft
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Declared status fields

These values are copied from the task definition. They do not establish current execution or scientific qualification.

| Field | Declared value |
| --- | --- |
| Stage | Registered construction draft |
| Runnable | No |
| Reference results qualified | No |
| Scientifically qualified | No |
| Submission ready | No |

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 11104 bytes; SHA-256 `adde2ccdd1e6366bbd83c53a31fb2d94a2df41faa9df5a878c18df702a8a93bd`.
- [Registration and provenance](../../../docs/provenance/registrations/expansion-20261113/registry.json)

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Implementation artifacts

- [Complete support evaluator](implementations/complete-support-evaluator) — Complete support evaluator.
  Scope: Complete normalized 79-infant probability endpoint, exact causal EEG packets and equal-infant Brier comparisons. Generated controls and source review do not verify authentic EDF/annotation alignment, input quality flags, reference competence, protected execution or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/ktapani/Neonatal_Seizure_Detection)
- [Code](https://github.com/ktapani/Neonatal_Seizure_Detection/tree/1a59e4b414f28aba52e61c3360fdc324199071b4)
- [Data](https://zenodo.org/records/4940267)
- [Paper](https://www.nature.com/articles/sdata201939)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
