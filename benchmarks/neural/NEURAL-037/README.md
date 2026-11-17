# Acquisition-local held-condition calcium response prediction

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-037`
- **Track:** Neural-data understanding
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

Measured held-condition calcium response values on each acquisition’s native frame grid, aggregated only by the original declared target rule. The exact mean/trajectory reduction must be recovered from its absent scorer; test-condition means cannot be supplied as predictors.

**Source delivery:** partial\_delivery. The historical full12 route predicts acquisition-local condition means over native frames, which is narrower than visual/opto-combination and animal-transfer generalization. Its source and grader are absent here; unknown mouse mapping and physical timing preclude the broader claim.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_delivered | Proposed no-tools numeric or visual presentation of the same permitted measurements specified above. No such participant transport is present. Preserve source support and permitted covariates; remove target values and answer-bearing metadata, except measured outcomes explicitly permitted in an investigation. | Define a bounded complete observation presentation and response collector; do not convert programme scores into direct-observation performance. |
| Typed viewer | not\_delivered | Potential typed rendering of calcium traces, morphology/coactivity summaries or condition comparisons appropriate to this endpoint; current source has no typed viewer. Only fixed render/selection actions return visuals; query hidden targets, raw evaluator files and unrestricted source lookups stay unavailable. | Implement audited task-specific image transport and complete answer collection; no viewer/model result exists here. |
| Tool assisted | not\_delivered | Proposed per-case numerical investigation using the same permitted observations, fixed numerical/model tools and accounted budget. Declare fit/analysis actions and reset state at the biological case boundary; no private evaluator feedback. | No matched interactive investigator transport is delivered; a programme/controller declaration alone does not implement this mode. |
| Frozen program | not\_delivered | A historical frozen-program declaration exists, but its named executable/producer/scorer source is absent from this current checkout. Future recovered programme must freeze before query access and preserve the exact declared complete scope; metadata flags do not establish a runnable mode. | Recover the named source/dependency closure and exact public input contract before executing or scoring. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 17382 bytes; SHA-256 `b774842af7d69259674a5087147e81d80f36ef8032f52bf8b2355529e93bc694`.
- [Preserved legacy runtime declaration](implementations/registered-runtime/manifest.json)
- [Legacy declaration package](implementations/registered-runtime)

This preserved declaration is lineage, not current execution qualification. Its historical paths may describe the source snapshot.

## Implementation artifacts

- [Registered runtime](implementations/registered-runtime) — Catalog registered source package.
  Scope: This is the source package currently selected by the published catalog; current does not assert executable/scientific qualification.
- [Condition viewer v1](implementations/condition-viewer-v1) — Reviewed task source component.
  Scope: Condition-viewer observation and response-collection source for the existing NEURAL-037 task. Registration covers the accepted source and its generated controls only; original task, comparison, runtime and scientific limits remain. Authentic input delivery, provider/model execution, participant isolation and scientific performance are unqualified.
- [Condition endpoint v1](implementations/condition-endpoint-v1) — Reviewed source component.
  Scope: Recovered complete-condition endpoint. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Source](https://doi.org/10.1016/j.neuron.2025.12.024)
- [Source](https://zenodo.org/api/records/18726362)
- [Source](https://zenodo.org/api/records/18726362/files/sequenceFiltering.zip/content)
- [Source](https://zenodo.org/records/18726362)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
