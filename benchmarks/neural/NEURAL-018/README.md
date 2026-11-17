# Causal motor-population forecasting

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-018`
- **Track:** Neural-data understanding
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

Observed integer spike counts for all 182 units in 40 future 5 ms bins, relative edges 450…645 ms.

**Source delivery:** partial\_delivery. The current scorer supports genuine future-count predictions on a complete 574-trial panel; legacy programme qualification is recorded but its runner is not delivered in this task folder. Known condition labels and retrospective movement alignment limit a causal-neural interpretation.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_delivered | Proposed per-trial numerical counts or fixed raster with all 40×182 positive future expected counts; no no-tools participant transport is supplied. Any future direct arm must receive exactly the selected permitted observation and calibrated units, with no decoder, Python, source lookup, target or score access. | Freeze a feasible complete per-case observation and response representation without silently changing the target.; Deliver and qualify a no-tools transport and complete answer collector before a direct-understanding claim. |
| Typed viewer | not\_delivered | Proposed typed raster/time-window inspection of the same selected neural observations; no viewer is delivered for this registration. Only admitted rendered views; raw numerical/model operations would belong to the tool-assisted condition. Query targets and source identities remain inaccessible. | Implement task-specific renderer, restricted actions and complete responses.; Verify rendered observations preserve required time/unit information and run a separately identified viewer evaluation. |
| Tool assisted | not\_delivered | Only an external numerical investigation could currently produce the submission; the artifact scorer does not supply a case-adaptive participant loop. Match observations, calibration, decoder access and cumulative compute against the fixed programme; freeze shared preparation, reset case state and prevent target/score feedback. | Deliver a bounded per-case participant loop with authenticated observation and answer lineage. |
| Frozen program | not\_delivered | The current package accepts prediction artifacts or provides reference routines; it does not deliver the candidate programme lifecycle. Freeze source, fitting, selection and permitted query adaptation before assessment access; authentic target custody and runtime qualification remain external. | Recover or implement the candidate producer and fit/freeze/predict/close lifecycle before calling the artifact score a programme evaluation. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 19353 bytes; SHA-256 `0328f6cbfef32141131d80d1e825afb98a9293cb76057ff8e6ae0c23b7a6211f`.
- [Preserved legacy runtime declaration](implementations/registered-runtime/manifest.json)
- [Legacy declaration package](implementations/registered-runtime)

This preserved declaration is lineage, not current execution qualification. Its historical paths may describe the source snapshot.

## Implementation artifacts

- [Registered runtime](implementations/registered-runtime) — Catalog registered source package.
  Scope: This is the source package currently selected by the published catalog; current does not assert executable/scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Source](https://api.dandiarchive.org/api/assets/26e85f09-39b7-480f-b337-278a8f034007/)
- [Source](https://api.dandiarchive.org/api/dandisets/000128/versions/0.220113.0400/)
- [Source](https://dandiarchive.org/dandiset/000128/0.220113.0400)
- [Source](https://doi.org/10.1038/nature11129)
- [Source](https://github.com/neurallatents/nlb_tools)
- [Source](https://raw.githubusercontent.com/neurallatents/nlb_tools/42f8410b88e12db136910fa2f888b025ea0aa2ae/nlb_tools/evaluation.py)
- [Source](https://raw.githubusercontent.com/neurallatents/nlb_tools/42f8410b88e12db136910fa2f888b025ea0aa2ae/nlb_tools/make_tensors.py)
- [Source](https://raw.githubusercontent.com/neurallatents/nlb_tools/42f8410b88e12db136910fa2f888b025ea0aa2ae/nlb_tools/nwb_interface.py)
- [Source](https://raw.githubusercontent.com/neurallatents/nlb_tools/main/README.md)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
