# Attempted-speech phoneme-sequence decoding

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-013`
- **Track:** Neural-data understanding
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

The source phoneme sequence for each retained attempted-speech trial, including the declared word-boundary symbol and edit denominator policy.

**Source delivery:** design\_only. The assigned registered-runtime artifact is a historical declaration with empty entrypoints and unscored full45 semantics; its referenced authoring paths are not present in this task delivery. It does not deliver a usable phoneme evaluator or qualified programme. The adjacent NEURAL-014 implementation is a different calibration protocol and cannot silently substitute.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_delivered | Direct numerical interpretation of a complete 512-feature trial would require learned mapping and a declared demonstration budget; no such observation-only condition is delivered. Only the declared observation/demonstration context, no external tools or evaluator feedback; a new direct condition needs an independently frozen view and complete output identity. | No delivered participant condition establishes this mode for the same scientific target. |
| Typed viewer | not\_delivered | A feature heatmap may aid inspection but has no delivered validated mapping to phoneme sequences. A viewer must preserve full observations and score the same sequence target to be comparable. Only typed render/navigation actions with audited limits; no raw arrays, labels, filenames or external source retrieval returned to the participant. | No delivered participant condition establishes this mode for the same scientific target. |
| Tool assisted | not\_delivered | A tool-assisted per-trial decoder investigation is possible with declared checkpoints and equal inputs; no active case broker or scorer is delivered here. Same permitted observations, frozen checkpoint tools and accounted compute as the compared arm; case state and feedback policy must be fixed before query. | No delivered participant condition establishes this mode for the same scientific target. |
| Frozen program | not\_delivered | Historical manifest describes one frozen fit and every pointwise query, but referenced programme bodies/entrypoint are not delivered and results are explicitly unscored. Freeze code and fitting/adaptation recipe before queries; admit only explicitly allowed labels/calibration, retain all failed/incomplete cases. | No delivered participant condition establishes this mode for the same scientific target. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 41348 bytes; SHA-256 `d605442b20543a9ae38c5d4fc53d8529b9406f62a96aadf611419ec23a9769fd`.
- [Preserved legacy runtime declaration](implementations/registered-runtime/manifest.json)
- [Legacy declaration package](implementations/registered-runtime)

This preserved declaration is lineage, not current execution qualification. Its historical paths may describe the source snapshot.

## Implementation artifacts

- [Registered runtime](implementations/registered-runtime) — Catalog registered source package.
  Scope: This is the source package currently selected by the published catalog; current does not assert executable/scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Source](https://datadryad.org/api/v2/datasets/doi%3A10.5061%2Fdryad.dncjsxm85)
- [Source](https://datadryad.org/api/v2/versions/374060/files)
- [Source](https://doi.org/10.1056/NEJMoa2314132)
- [Source](https://doi.org/10.5061/dryad.dncjsxm85)
- [Source](https://github.com/Neuroprosthetics-Lab/nejm-brain-to-text)
- [Source](https://huggingface.co/api/datasets/yw784/brain-to-text-25-competition)
- [Source](https://raw.githubusercontent.com/Neuroprosthetics-Lab/nejm-brain-to-text/980a5b7e96392210edf976d76bdb5d15d2e0e62b/data/t15_copyTaskData_description.csv)
- [Source](https://raw.githubusercontent.com/Neuroprosthetics-Lab/nejm-brain-to-text/980a5b7e96392210edf976d76bdb5d15d2e0e62b/model_training/dataset.py)
- [Source](https://raw.githubusercontent.com/Neuroprosthetics-Lab/nejm-brain-to-text/980a5b7e96392210edf976d76bdb5d15d2e0e62b/model_training/evaluate_model_helpers.py)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
