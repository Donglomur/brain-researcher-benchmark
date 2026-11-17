# Stable population dynamics across days

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-024`
- **Track:** Neural-data understanding
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

Observed integer extracellular counts in the next 20 ms bin for all 96 M1 electrode channels; candidate outputs are strictly positive expected counts per bin. Evidence for adaptation is a held-out likelihood contrast, not agreement with a claim that dynamics are stable.

**Source delivery:** partial\_delivery. Current publication retains a precise historical count-forecast declaration and delivery manifest, but no numerical count scorer, protocol parser, candidate controller or asset bodies under this task. The documented finite target is relevant to the original neural-history question; source availability and broad across-day stability remain unestablished until those declared components are recovered and verified.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_delivered | A no-tools bounded count-history view could test next-bin expectation judgments if complete episode support and output dimensionality were preserved. Only lawful preceding observations; exact expected-count response and feedback policy must be fixed before any trial. | No direct observation transport or complete-response collection; current 22,100-round quantitative task is not a validated visual interpretation task. |
| Typed viewer | not\_delivered | Potential typed raster/history visualization without raw-array or future-count access. A viewer cannot reveal current target counts before a 96-value prediction is committed; any reduced-channel/window endpoint is an explicit scope revision. | No viewer renderer, typed actions or causal answer/observation binding. |
| Tool assisted | not\_delivered | Proposed per-case neural-history investigation with numerical tools and fixed decoder models under the same lawful-prefix protocol. Freeze tool/checkpoint access and adaptation/compute; verify numeric contrasts independently without privileged future data. | No present tool-using actor controller or investigation evidence scorer; historical references are not matched agent/tool trials. |
| Frozen program | not\_delivered | Historical precommitted programme procedure with lawful-prefix updates and complete next-bin outputs. Freeze executable and update policy before target stream; fixed programme does not mean fixed weights, and actual current/future counts must remain outside candidate mounts. | Historical registered runtime/protocol/scorer source and asset bodies are absent from current publication; recover and verify them before exposing this mode. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 32718 bytes; SHA-256 `465c462ce967e021cb9a99ec4ac5f21e6e11235ba099c3f9097a96753af9244a`.
- [Preserved legacy runtime declaration](implementations/registered-runtime/manifest.json)
- [Legacy declaration package](implementations/registered-runtime)

This preserved declaration is lineage, not current execution qualification. Its historical paths may describe the source snapshot.

## Implementation artifacts

- [Delivery](contracts/delivery) — Task contract.
  Scope: Keep mixed current/source-predecessor/context members together; this map does not select a new operative version or qualify execution.
- [Registered runtime](implementations/registered-runtime) — Catalog registered source package.
  Scope: This is the source package currently selected by the published catalog; current does not assert executable/scientific qualification.
- [Complete count scorer v1](implementations/complete-count-scorer-v1) — Reviewed source component.
  Scope: Complete count likelihood scorer. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

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
