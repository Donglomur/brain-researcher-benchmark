# Marmoset retinal nonlinear contrast encoding and cross-stimulus generalization

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `marmoset-retinal-contrast-generalization`
- **Track:** Neural-data understanding
- **Registration:** Expansion draft
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

Protected per-cell spike counts at each 85 Hzprojector update and repeat-averaged responses, with physical event/grid alignment authenticated.

**Source delivery:** partial\_delivery. Condition-permitted training-count loading, complete declared-support protected numerical scoring and a constant-rate diagnostic are implemented. Authentic stimulus preparation, RF/reference fitting, protected participant lifecycle and matched interpretation packets remain unavailable or unqualified.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_suitable | Pure protected encoding cases contain stimuli rather than observed query neural activity; visible calibration traces would support a separately specified matched interpretation diagnostic. Exposing protected spikes to make a neural picture would disclose the scored target; current programme scores cannot establish direct understanding. | Define a nonleaking calibration-based or masked-observation interpretation estimand before enabling this mode. |
| Typed viewer | not\_suitable | No target-preserving viewer interpretation task is currently defined for stimulus-to-protected-response encoding. A calibration-only viewer could be a future matched condition, but protected target rasters/means must never be rendered. | Separate observation/target mask and complete view policy, not a renamed programme score. |
| Tool assisted | not\_delivered | Partial source components exist for condition-permitted training-count preparation, a constant-rate diagnostic and owner-only protected scoring; the complete tool-assisted task still lacks qualified matching stimuli and constrained fitting/execution. Source-only versus WN-assisted domains remain distinct. Calibration-only labels do not enforce downstream fitting. The owner scorer is a numerical API, not target custody or a sandbox, and the constant diagnostic is not the competent spatial-contrast reference. | Authentic complete stimuli/case packets, constrained condition-permitted fitting, competent references and protected participant/scorer integration. |
| Frozen program | not\_delivered | A complete declared-support constant predictor and owner-side protected scorer exist as source components; an arbitrary participant programme fit/freeze/predict lifecycle over qualified stimuli is not delivered. Freeze the full cell roster, permitted calibration route, fitting/normalization/smoothing and programme before protected queries. The pure source APIs cannot establish freeze chronology or deny target-file access; the constant diagnostic remains unqualified and is not the spatial-contrast reference. | Qualified stimulus preparation, protected participant fit/freeze/predict/score lifecycle and competent reference qualification. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 34321 bytes; SHA-256 `9a716fa42aa1ac625e5d7fafd79d5dd3f7d49ac8bfb55957f8057d8efc2352b8`.
- [Registration and provenance](../../../docs/provenance/registrations/expansion-20261114/registry.json)

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Implementation artifacts

- [Training response](implementations/training-response) — Training response.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification.
- [Constant rate v1](implementations/constant-rate-v1) — Reviewed source component.
  Scope: Reviewed additive source component for the existing task. The package documentation and source contracts define its scope; source enrollment does not establish authentic-data execution or scientific qualification.
- [Protected scoring v1](implementations/protected-scoring-v1) — Reviewed source component.
  Scope: Protected response scoring. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Source](https://doi.gin.g-node.org/10.12751/g-node.3dfiti/)
- [Source](https://doi.gin.g-node.org/10.12751/g-node.t43ph1/)
- [Source](https://gin.g-node.org/doi/Sridhar_Gollisch_2025_Marmoset_RGC_Responses_Naturalistic_Movies)
- [Source](https://github.com/gollischlab/SpatiotemporalSCModel)
- [Source](https://github.com/open-retina/open-retina)
- [Source](https://huggingface.co/datasets/open-retina/nm_marmoset_data)
- [Source](https://huggingface.co/datasets/open-retina/wn_marmoset_data)
- [Source](https://open-retina.org/package_docs/datasets/sridhar_2025/)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
