# Somatosensory hand-velocity decoding

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-021`
- **Track:** Neural-data understanding
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

Measured x/y hand-velocity trajectory in m/s:30 bins per query, all 92 queries.

**Source delivery:** partial\_delivery. The full 92 trajectory producer source and deferred scorer exist, but no authentic complete producer/deferred-grade run or runtime qualification is established. The source targets retrospective velocity reconstruction with condition context, not prospective causal forecasting.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_delivered | Proposed per-trial numerical counts or fixed raster with all 30×2 signed velocity values; no no-tools participant transport is supplied. Any future direct arm must receive exactly the selected permitted observation and calibrated units, with no decoder, Python, source lookup, target or score access. | Freeze a feasible complete per-case observation and response representation without silently changing the target.; Deliver and qualify a no-tools transport and complete answer collector before a direct-understanding claim. |
| Typed viewer | not\_delivered | Proposed typed raster/time-window inspection of the same selected neural observations; no viewer is delivered for this registration. Only admitted rendered views; raw numerical/model operations would belong to the tool-assisted condition. Query targets and source identities remain inaccessible. | Implement task-specific renderer, restricted actions and complete responses.; Verify rendered observations preserve required time/unit information and run a separately identified viewer evaluation. |
| Tool assisted | not\_delivered | Only an external numerical investigation could currently produce the submission; the artifact scorer does not supply a case-adaptive participant loop. Match observations, calibration, decoder access and cumulative compute against the fixed programme; freeze shared preparation, reset case state and prevent target/score feedback. | Deliver a bounded per-case participant loop with authenticated observation and answer lineage. |
| Frozen program | source\_available | Precommitted executable and fitting recipe; training precedes query prediction. Freeze source, fitting, selection and permitted query adaptation before assessment access; authentic target custody and runtime qualification remain external. | Qualify the actual external data/runtime source closure and complete programme execution. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 19092 bytes; SHA-256 `d8bc2e852c4bb45b8bb78950f42275c2b6b81dccdb157207b50f21c3b9cb2136`.
- [Preserved legacy runtime declaration](implementations/registered-runtime/manifest.json)
- [Legacy declaration package](implementations/registered-runtime)

This preserved declaration is lineage, not current execution qualification. Its historical paths may describe the source snapshot.

## Implementation artifacts

- [Registered runtime](implementations/registered-runtime) — Catalog registered source package.
  Scope: This is the source package currently selected by the published catalog; current does not assert executable/scientific qualification.
- [Neural021 deferred grade](implementations/neural021-deferred-grade) — Task implementation source.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification.
- [Observation grade v1](implementations/observation-grade-v1) — Reviewed task source component.
  Scope: Accepted source and generated-control evidence only. Artifact enrollment does not change task IDs, access modes, runtime selection, submission readiness, reproduction or improvement qualification.
- [Paired observation grade v1](implementations/paired-observation-grade-v1) — Reviewed source component.
  Scope: Descriptive paired direct-observation and typed-viewer grading of complete original 92-query trajectories, with both histories admitted before one protected target capture and unchanged numerical scoring. Exposure summaries do not prove matched participant execution, actual image delivery, tool isolation, neural understanding or scientific readiness.
- [Participant transport v1](implementations/participant-transport-v1) — Reviewed source component.
  Scope: Reviewed participant transport source and generated controls for the existing NEURAL-021 task. Authentic runtime selection and scientific qualification remain separate.
- [Raster participant v1](implementations/raster-participant-v1) — Reviewed source component.
  Scope: Reviewed additive source component for the existing task. The package documentation and source contracts define its scope; source enrollment does not establish authentic-data execution or scientific qualification.
- [Publication mode repair v1](implementations/publication-mode-repair-v1) — Reviewed source component.
  Scope: Explicit public directory modes and bounded generated permission controls under restrictive umask; historical source manifests and private defaults remain preserved. Source/control enrollment does not establish Docker behavior, authentic-data correctness, native runtime qualification, model outcomes or scientific qualification.
- [Paired count delivery v1](implementations/paired-count-delivery-v1) — Reviewed source component.
  Scope: NEURAL-021 exact-count visual delivery. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Source](https://api.dandiarchive.org/api/assets/ded26b6c-418d-43f5-8a37-dfd072c2dbd4/)
- [Source](https://api.dandiarchive.org/api/dandisets/000127/versions/0.220113.0359/)
- [Source](https://dandiarchive.org/dandiset/000127/0.220113.0359)
- [Source](https://doi.org/10.7554/eLife.48198)
- [Source](https://github.com/neurallatents/nlb_tools)
- [Source](https://raw.githubusercontent.com/neurallatents/nlb_tools/42f8410b88e12db136910fa2f888b025ea0aa2ae/nlb_tools/evaluation.py)
- [Source](https://raw.githubusercontent.com/neurallatents/nlb_tools/42f8410b88e12db136910fa2f888b025ea0aa2ae/nlb_tools/make_tensors.py)
- [Source](https://raw.githubusercontent.com/neurallatents/nlb_tools/42f8410b88e12db136910fa2f888b025ea0aa2ae/nlb_tools/nwb_interface.py)
- [Source](https://raw.githubusercontent.com/neurallatents/nlb_tools/main/README.md)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
