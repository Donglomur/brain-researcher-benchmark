# Continuous reaching across recording days

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-023`
- **Track:** Neural-data understanding
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

Measured trailing 20 ms finger velocity in m/s, x then y, at each assessment endpoint. This is continuous movement reconstruction from neural observations, not reproduction of a published score table.

**Source delivery:** partial\_delivery. A complete numerical artifact scorer is present for one exposed Indy day pair and 22,091 trailing-velocity endpoints. Exact prepared arrays remain operator-provisioned; the registered historical program runner and legacy scorer dependency are absent from the published source. The source-wide later-session/second-animal claim and matched investigation modes remain unfinished.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_delivered | Proposed numeric spike-raster/count view plus fixed labeled calibration, with a complete structured velocity response. No numerical/model tools or evaluator feedback; a reduced visual case would be a separately declared endpoint, not a score on the full current batch. | No no-tools observation/answer transport or tested model trial. |
| Typed viewer | not\_delivered | Potential typed raster/count-history visualization for the same designated observations; dense 22,091-by-96 full support must not silently become a hand-picked example set. Typed bounded rendering only, with no raw-array/target return and fixed response coverage. | No typed viewer, rendering/answer binding or complete-support viewer protocol. |
| Tool assisted | not\_delivered | Proposed per-session numerical/model-assisted investigation of transfer, calibration and neural dependence; external artifact scorer can grade resulting full-support predictions. Same data, calibration labels, checkpoint access and accounted compute as comparison; numerical claims must be recomputed without evaluator feedback. | No current actor/tool controller or matched investigation outcome grader; artifact scoring alone supplies neither. |
| Frozen program | not\_delivered | Historical one-file frozen-program route receives source, calibration and full target-free assessment batch. Commit program and fitting recipe before assessment; full-batch assessment counts are permitted; scoring must follow producer shutdown with private assets excluded. | Historical runner source and required local execution dependencies absent from current publication; only the prediction artifact scorer is delivered. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Recorded public evidence

Each record keeps the scope of its original report. It is not current runtime qualification.

- [Historical programme control](../../../docs/provenance/execution/historical-evidence-v1/profiles.json): One animal and two exposed recording days; 18,691 training, 2,991 calibration and 22,091 assessment rows; 96 channels and 20 ms bins.

Inspect conditions, metrics and limits with `python3 scripts/neurobench.py evidence NEURAL-023`. Programme evidence does not establish direct interpretation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 32026 bytes; SHA-256 `b831d7047d7c6e658f497afa80d23bce826a3f2cf5d4f4120a980473d0cc77dd`.
- [Preserved legacy runtime declaration](implementations/registered-runtime/manifest.json)
- [Legacy declaration package](implementations/registered-runtime)

This preserved declaration is lineage, not current execution qualification. Its historical paths may describe the source snapshot.

## Implementation artifacts

- [Delivery](contracts/delivery) — Task contract.
  Scope: Keep mixed current/source-predecessor/context members together; this map does not select a new operative version or qualify execution.
- [Registered runtime](implementations/registered-runtime) — Catalog registered source package.
  Scope: This is the source package currently selected by the published catalog; current does not assert executable/scientific qualification. Repository-depth locator corrected after relocation; 1 local scorer dependency is absent from the public source baseline and relocation ledger. Historical dependency names/pins remain unchanged. This bridge has not been made runnable or newly qualified by the reorganization. Other task artifacts are outside this finding.
- [Submitted program v1](implementations/submitted-program-v1) — Reviewed task source component.
  Scope: Accepted source and generated-control evidence only. Artifact enrollment does not change task IDs, access modes, runtime selection, submission readiness, reproduction or improvement qualification.
- [Participant delivery v1](implementations/participant-delivery-v1) — Reviewed source component.
  Scope: Participant delivery for the fixed Indy transfer. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Source](https://doi.org/10.1088/1741-2552/aa9e95)
- [Source](https://doi.org/10.5281/zenodo.3854034)
- [Source](https://github.com/joel99/ndt3)
- [Source](https://github.com/neurallatents/nlb_tools)
- [Source](https://raw.githubusercontent.com/joel99/ndt3/877f9f5edbcd47f20af6e6c0ba11926da7a22354/context_general_bci/tasks/rtt.py)
- [Source](https://zenodo.org/api/records/3854034)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
