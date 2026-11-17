# Somatosensory population co-smoothing

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-020`
- **Track:** Neural-data understanding
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

Observed held-out-unit spike counts on fixed 600 msmovement-onset windows for the declared evaluation rows.

**Source delivery:** partial\_delivery. A substantive tensor preparation/scoring component exists for complete 826-row/65-unit Area 2 training-asset inputs, but it does not read or authenticate NWB conversion. Active/perturbed reporting is implemented; leave-condition-out generalization is not frozen.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_delivered | Proposed per-trial numerical counts or fixed raster with all required time×withheld-unit expected counts; no no-tools participant transport is supplied. Any future direct arm must receive exactly the selected permitted observation and calibrated units, with no decoder, Python, source lookup, target or score access. | Freeze a feasible complete per-case observation and response representation without silently changing the target.; Deliver and qualify a no-tools transport and complete answer collector before a direct-understanding claim. |
| Typed viewer | not\_delivered | Proposed typed raster/time-window inspection of the same selected neural observations; no viewer is delivered for this registration. Only admitted rendered views; raw numerical/model operations would belong to the tool-assisted condition. Query targets and source identities remain inaccessible. | Implement task-specific renderer, restricted actions and complete responses.; Verify rendered observations preserve required time/unit information and run a separately identified viewer evaluation. |
| Tool assisted | not\_delivered | Only an external numerical investigation could currently produce the submission; the artifact scorer does not supply a case-adaptive participant loop. Match observations, calibration, decoder access and cumulative compute against the fixed programme; freeze shared preparation, reset case state and prevent target/score feedback. | Deliver a bounded per-case participant loop with authenticated observation and answer lineage. |
| Frozen program | not\_delivered | The current package accepts prediction artifacts or provides reference routines; it does not deliver the candidate programme lifecycle. Freeze source, fitting, selection and permitted query adaptation before assessment access; authentic target custody and runtime qualification remain external. | Recover or implement the candidate producer and fit/freeze/predict/close lifecycle before calling the artifact score a programme evaluation. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 19553 bytes; SHA-256 `ca96481c914df4cd6345cf28047fdc3b8133ac40f3a74db078926ed25414711d`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Task implementation.
  Scope: Prepares the complete declared 826-trial/65-unit Area2 training-asset tensor packet, scores active/perturbed Poisson co-bps, and provides training-mean and source-derived smoothing controls. Native NWB conversion, mask/condition authenticity, prospective condition-transfer scope, authentic reference performance and protected scientific admission remain unqualified; portable byte-pinned upstream metric tests are engineering evidence only.
- [Native spike preparation v1](implementations/native-spike-preparation-v1) — Reviewed source component.
  Scope: Native Area2 spike preparation. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

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
