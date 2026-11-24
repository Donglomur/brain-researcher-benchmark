# Omission-conditional calcium population trajectory prediction

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-063`
- **Track:** Neural-data understanding
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

Three native-clock population-mean dF/F values in \[0,0.2),\[0.2,0.4),\[0.4,0.6) seconds after scheduled omission, each minus the mean of the final \[-0.2,0) history bin.

**Source delivery:** partial\_delivery. The archive implements a three-bin population-average dF/F forecasting target with complete preparation/scoring source and F/I condition interfaces. The original cell/population wording overstates its cell resolution: all fixed ROI columns are averaged before prediction. Deployment, authentic event support, reference competence and actual solver transport remain unqualified.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_delivered | A finite 12-bin numeric history with preceding context could support a direct no-tools three-value response, but no such transport is supplied. Keep the same baseline and eligible events, prevent target-frame or source lookup, and declare demonstrations separately. | Implement complete numeric/context delivery, query-bound responses and matched demonstration conditions. |
| Typed viewer | not\_delivered | A plot of the same population-history bins could support typed zoom/inspection without exposing targets; no renderer exists here. No raw target arrays or future traces; a cell-level viewer would change the delivered target and information. | Implement and qualify restricted rendering and complete image-to-answer transport. |
| Tool assisted | source\_available | I source interface supports per-event investigation with general numerical tools or the matched trained reference tool on the declared T/N view. Same complete query schedule, tool allowance and accounted resources as its comparator; event state and protected targets require independently qualified isolation. | Provision actual controller/model assets and trusted per-event containment; complete reference tool qualification. |
| Frozen program | source\_available | F source interface freezes the prediction recipe before query events and uses the same T/N information and G/R tool condition. Development and query separated; no query labels, query-directed tuning or undeclared cross-event adaptation. | Execute authentic preparation/reference stages and qualify full programme runtime. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 18119 bytes; SHA-256 `24e10b7afc2ec5ea20370c12a9d119806025af4fdaee644513fab6db977935a6`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Original metadata qualification and remaining cohort work](docs/original-metadata-qualification.md)
- [Original metadata qualification evidence](docs/original-metadata-evidence.json)

## Implementation artifacts

- [Neural 063](implementations/neural-063) — Task source archive.
  Scope: Source archive remains an implementation resource; relocation does not establish configured deployment or scientific qualification.
- [Contained vlen v1](implementations/contained-vlen-v1) — Reviewed source component.
  Scope: Contained VLEN reader, fixed export and controller source with configurable validated locators and strict independently selected native authority. It adopts the accepted cleanup reader without modifying it and preserves the original 107 mice, 703 sessions, 1936 planes and 73/15/19 split. Saved generated controls use invented data; original-array acquisition, actual Linux/container lifecycle, real OOM/timeout descendant cleanup, full-cohort scientific completion and benchmark readiness remain unestablished. Inactive templates and source enrollment do not activate a runtime.
- [Full census v1](implementations/full-census-v1) — Reviewed source component.
  Scope: Separate layouts, metadata/support and all-source-column physical chunk census source for the full original cohort. A missing/failed/unattempted plane holds its session and cohort; first failure stops a stage with explicit tail dispositions. Unknown VLEN/unbounded session representations are refused before decoding. Original scientific modules and endpoints are unchanged; no authentic cohort census, projection/provider operation, model result or benchmark readiness is established.
- [Original qualifier v1](implementations/original-qualifier-v1) — Reviewed source component.
  Scope: One-original acquisition and local-versus-range array/transport comparison source with an explicitly synthetic25721-byte fixture. It preserves original runtime/scoring and the B19 range-source dependency. Authentic CLI/supervisor admission and actual acquisition are separate; no all-plane/full-cohort, native understanding or benchmark completion claim.
- [Restricted viewer v1](implementations/restricted-viewer-v1) — Reviewed source component.
  Scope: Restricted observation rendering for all supplied paired rows in the declared 19-query-mouse panel. Original eligible schedule, frame/target separation, participant execution and scientific understanding remain unqualified.
- [Versioned range v1](implementations/versioned-range-v1) — Reviewed source component.
  Scope: Alternative operator preparation reads the same fixed-version NWB objects with explicit range identity and custody. It preserves all107mice/703sessions/1936planes, native ROI/clock and15-bin endpoint support, while explicitly leaving whole-object BLAKE2b verification false. All-cohort native layout/support, authentic comparison, canonical participant adoption and scientific qualification remain unestablished.
- [Direct numeric v1](implementations/direct-numeric-v1) — Reviewed source component.
  Scope: Direct numeric paired delivery. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Source](https://alleninstitute.org/legal/terms-use/)
- [Source](https://allensdk.readthedocs.io/en/latest/visual_behavior_optical_physiology.html)
- [Source](https://github.com/AllenInstitute/AllenSDK)
- [Source](https://raw.githubusercontent.com/AllenInstitute/AllenSDK/a56bd8ea7613a812334602b64746cdd30c325a96/LICENSE.txt)
- [Source](https://raw.githubusercontent.com/AllenInstitute/AllenSDK/a56bd8ea7613a812334602b64746cdd30c325a96/doc_template/examples_root/examples/nb/visual_behavior_load_ophys_data.ipynb)
- [Source](https://visual-behavior-ophys-data.s3.us-west-2.amazonaws.com/visual-behavior-ophys/manifests/visual-behavior-ophys_project_manifest_v1.1.0.json)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
