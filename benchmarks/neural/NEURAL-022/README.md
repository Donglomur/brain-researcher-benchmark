# Active-versus-passive sensory coding

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-022`
- **Track:** Neural-data understanding
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

Two measured nominal velocity components in m/s per query, at the declared retrospective 120 msmovement-onset target.

**Source delivery:** partial\_delivery. Current source supports arbitrary complete 92-row velocity artifacts and a passive 40 query primary loss. It preserves a fixed active-versus-passive-reference diagnostic, but does not enforce matched kinematics, candidate active-only fitting or the broader causal-coding investigation.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_delivered | Proposed per-trial numerical counts or fixed raster with one finite 2 component velocity prediction; no no-tools participant transport is supplied. Any future direct arm must receive exactly the selected permitted observation and calibrated units, with no decoder, Python, source lookup, target or score access. | Freeze a feasible complete per-case observation and response representation without silently changing the target.; Deliver and qualify a no-tools transport and complete answer collector before a direct-understanding claim. |
| Typed viewer | not\_delivered | Proposed typed raster/time-window inspection of the same selected neural observations; no viewer is delivered for this registration. Only admitted rendered views; raw numerical/model operations would belong to the tool-assisted condition. Query targets and source identities remain inaccessible. | Implement task-specific renderer, restricted actions and complete responses.; Verify rendered observations preserve required time/unit information and run a separately identified viewer evaluation. |
| Tool assisted | not\_delivered | Only an external numerical investigation could currently produce the submission; the artifact scorer does not supply a case-adaptive participant loop. Match observations, calibration, decoder access and cumulative compute against the fixed programme; freeze shared preparation, reset case state and prevent target/score feedback. | Deliver a bounded per-case participant loop with authenticated observation and answer lineage. |
| Frozen program | not\_delivered | The current package accepts prediction artifacts or provides reference routines; it does not deliver the candidate programme lifecycle. Freeze source, fitting, selection and permitted query adaptation before assessment access; authentic target custody and runtime qualification remain external. | Recover or implement the candidate producer and fit/freeze/predict/close lifecycle before calling the artifact score a programme evaluation. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 19649 bytes; SHA-256 `18404f98363a0766f0224928093fa6d439377d7e87fbebfa61710c68da65c295`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Implementation artifacts

- [Artifact grading](implementations/artifact-grading) — Artifact grading.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification.
- [Public control v1](implementations/public-control-v1) — Reviewed source component.
  Scope: Public active-only controls. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

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
