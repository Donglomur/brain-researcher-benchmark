# Retrospective wheel-speed decoding beyond context and neural alignment controls

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-060`
- **Track:** Neural-data understanding
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

The original 50 absolute wheel-speed samples at 50 Hz in \[movement\_onset,movement\_onset+1 second); each sample retains its actual offset.

**Source delivery:** delivered\_named\_scope. Current full programme source implements absolute wheel-speed decoding on all 29 evaluation sessions with matched nuisance/joint/test-neural-shift arms. This is an explicit narrowing of the historical wheel/choice and causal-context wording: choice is not delivered, and processed history plus simultaneous spikes is retrospective. Full authentic inputs, native execution and scientific competence remain unqualified.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_delivered | Prospective fixed no-tools representation of the full simultaneous neural tensor and matched context, returning all 50 speed values. Representational changes must retain the original observations and full target support; cannot quietly replace dense prediction with a qualitative plot question. | No no-tools full-context response transport or demonstrated representation feasibility. |
| Typed viewer | not\_delivered | Prospective raster/history viewer with typed navigation and complete numeric response collection. Rendered observations only; no hidden wheel target trace, raw arrays or unbounded computation. | No typed image renderer/transport; plot subsampling would require an explicit changed-observation condition. |
| Tool assisted | source\_available | I workflow investigates one session/role with Python and bounded provider actions on original train/validation and unlabeled test input. Seal method/typed recipe, terminate investigation, refit fresh on train+validation and replay original/shifted test from identical state. No score feedback. | Actual provider/native/image qualification and external process/semantic-method observation. |
| Frozen program | source\_available | F workflow freezes global source before dataset numerical exposure, then fits each session separately with its calibration data. No state transfer across sessions; no test-batch fitting in paired replay; identical initial method/state/RNG and internal paths in original/shifted inference. | Complete authentic data/reference work and admitted full-workload resources. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 16847 bytes; SHA-256 `60866b21ed78fb576ad368c3964672fc55c53ab6e8720d140e74ab4e34534ec0`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Implementation artifacts

- [Full central programme](implementations/full-central-programme) — Task implementation.
  Scope: Keep mixed current/source-predecessor/context members together; this map does not select a new operative version or qualify execution.
- [Delivery](contracts/delivery) — Task contract.
  Scope: Keep mixed current/source-predecessor/context members together; this map does not select a new operative version or qualify execution.
- [Current layout runtime v1](implementations/current-layout-runtime-v1) — Reviewed source component.
  Scope: Current-layout full runtime source. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Source](https://brainbench-org.github.io/ibl-bwb/guides/dataset.html)
- [Source](https://doi.org/10.1038/s41586-025-09235-0)
- [Source](https://github.com/brainbench-org/ibl-bwb)
- [Source](https://raw.githubusercontent.com/brainbench-org/ibl-bwb/6fbd666fe8170a2165f5198c1f490911424a654d/src/ts1/models/single_session/linear/linear.py)
- [Source](https://raw.githubusercontent.com/brainbench-org/ibl-bwb/6fbd666fe8170a2165f5198c1f490911424a654d/src/ts1/ts1_dataset.py)
- [Source](https://registry.opendata.aws/ibl-brain-wide-bench/)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
