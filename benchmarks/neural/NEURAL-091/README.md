# Stimulus-family response prediction for calibrated Neuropixels units

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-091`
- **Track:** Neural-data understanding
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

Protected integer spike count over each eligible presentation after invalid neural intervals are removed; exposure is the remaining valid duration.

**Source delivery:** partial\_delivery. An exposure-aware adapter, train-only controls and genuine held-out spike scorer exist. Complete authenticated native export, permitted stimulus content, competent stimulus-transfer reference and participant execution remain missing, so the old not\_implemented wording is superseded only for this construction component.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_delivered | Direct quantitative prediction could use calibration counts and allowed stimulus/state tables; a screenshot of spikes would reveal the target and changes the encoding task. Any future no-tools condition must expose only the allowed observation and a fixed calibration context; participant code, source lookup and evaluator feedback are excluded. | No bounded direct-response representation, participant transport or complete response collection is delivered. |
| Typed viewer | not\_delivered | A task-specific rendered observation with typed navigation would be a separate access condition, not evidence supplied by the programme. No current image-only action API; future views must preserve eligible channels/time/support without returning raw arrays or answer-bearing metadata. | No typed viewer or viewer-model evaluation for this task. |
| Tool assisted | not\_delivered | Numerical analysis could fit/calibrate on public training rows and predict query rates. Public/private files are an interface, not a sandbox; query counts/source bundle must remain unavailable and any model tools must be matched. | No protected adaptive participant transport or per-case episode budget. |
| Frozen program | not\_delivered | The scorer accepts predictions and supplies fixed controls; a general frozen candidate fit/inference lifecycle is not delivered. Freeze candidate and fit recipe before query; preserve the complete keyed cohort and pre-outcome eligibility. | Candidate lifecycle and authenticated native input/operator execution. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 17043 bytes; SHA-256 `e82fb3edeceadb5297038eb1a3c8e2d03737ceb522c7598292ff07fbee16037a`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Task implementation.
  Scope: Prepares exposure-aware Neuropixels exports with stimulus-family/repeat/time guards, computes train-only rate/state controls, and scores exact predictions with mouse-macro Poisson bits per spike. Authentic recording/presentation identity, SDK/NWB and clock compatibility, complete allowed stimulus inputs, protected execution, competent stimulus-transfer references, rights and scientific qualification remain held.
- [Complete roster evaluator v2](implementations/complete-roster-evaluator-v2) — Reviewed source component.
  Scope: Complete declared-roster scoring. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Source](https://brain-map.org/our-research/circuits-behavior/visual-coding)
- [Source](https://github.com/AllenInstitute/AllenSDK)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
