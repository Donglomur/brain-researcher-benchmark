# Event-cued retrospective reach-parameter decoding from ECoG

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-049`
- **Track:** Neural-data understanding
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

Primary: the released intervals/reaches Reach\_angle\_degrees folded vertical angle, in degrees within \[-90,90\], not circular heading. Complete secondary targets are Reach\_magnitude\_px and Onset\_speed\_px\_per\_sec from the same row.

**Source delivery:** partial\_delivery. The current definition explicitly adopts the supplied retrospective event-cued reach-angle scope with complete magnitude and onset-speed companions. Its ±5-second observations and within-patient day split differ from the preserved original causal continuous wrist-velocity target, which remains unmet history. Native census and execution are unqualified.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_delivered | Potential numeric or rendered single-event ECoG view would need an explicit finite response protocol on the same retrospective target. No direct result can be inferred from programmes operating on 5000×channel arrays and learned case-local state. | No no-tools observation transport, rendering/quantization policy or demonstration protocol. |
| Typed viewer | not\_delivered | Potential bounded event waveform/spectrum viewer, preserving complete permitted channels/time support. Only typed actions over released neural observation projection; no pose/target/raw NWB access. | No typed-viewer source or response collection for this task. |
| Tool assisted | source\_available | I source authors/edits analyses within a fresh held-day context; optional T1 supplies the exact case-local decoder. Same data, full label-free query batch and budgets as F; no held targets, cross-fold state or arbitrary original NWB reads. | Physical isolation, authentic complete data and reference/model custody remain unqualified. |
| Frozen program | source\_available | F source seals arbitrary prediction code and fitting/batch-adaptation recipe before study-value exposure. Training within an isolated held-day context is allowed; post-exposure unrestricted code generation is I, not F. | Native source-route qualification, full reference graph feasibility and complete observed execution. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 16630 bytes; SHA-256 `808819f6161dbeb151ed52edb73fe28b5a535bb31b380f6f1e9a4503d775e1b2`.
- [Preserved legacy runtime declaration](implementations/registered-runtime/manifest.json)
- [Legacy declaration package](implementations/registered-runtime)

This preserved declaration is lineage, not current execution qualification. Its historical paths may describe the source snapshot.

## Implementation artifacts

- [Programme source](implementations/programme-source) — Task implementation.
  Scope: Keep mixed current/source-predecessor/context members together; this map does not select a new operative version or qualify execution.
- [Registered runtime](implementations/registered-runtime) — Catalog registered source package.
  Scope: This is the source package currently selected by the published catalog; current does not assert executable/scientific qualification.
- [Endpoint report v2](implementations/endpoint-report-v2) — Reviewed source component.
  Scope: Complete reach endpoint diagnostics. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Source](https://api.dandiarchive.org/api/dandisets/000055/versions/0.220127.0436/)
- [Source](https://dandiarchive.org/dandiset/000055)
- [Source](https://doi.org/10.1038/s41597-022-01280-y)
- [Source](https://github.com/BruntonUWBio/ajile12-nwb-data)
- [Source](https://raw.githubusercontent.com/BruntonUWBio/ajile12-nwb-data/f44ca6f6c51251b62b6f47492bba400472d4a7ba/Example_AJILE12_exploratory_analysis.ipynb)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
