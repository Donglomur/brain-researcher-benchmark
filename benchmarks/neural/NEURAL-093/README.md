# Sensory evidence decoding during decisions

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-093`
- **Track:** Neural-data understanding
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

Per-trial class derived from recorded left/right stimulus contrasts under an exact three-class mapping. The current manifest names the three-way target but does not supply that mapping; it must be recovered rather than guessed.

**Source delivery:** design\_only. The retained manifest specifies a complete 39-session, four-input-arm stimulus-evidence experiment but its current source entrypoint and scorer are absent from this task package. Historical two-arm developer runs do not qualify the replacement four-arm route. Recover the pinned executable and public case manifest, then authenticate the complete panel before execution.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_delivered | Proposed no-tools per-trial spike raster or fixed numerical first100ms observation with permitted context. Response must be a three-class probability vector; direct observation requires its own fixed rendering, training-example policy and output transport. | No direct numeric/image participant packet or complete response transport. |
| Typed viewer | not\_delivered | A future restricted spike-raster/wheel viewer could expose the same fixed observation window. Typed plots must not return raw hidden metadata, labels or later observations. | No093 typed viewer actions, rendering or response collection source. |
| Tool assisted | not\_delivered | Proposed per-case numerical/model-assisted investigation on the same four observation views. Frozen access/compute and label-free investigation per case; programme declaration alone is not this condition. | No current investigator transport with authenticated case inputs. |
| Frozen program | not\_delivered | Manifest-declared complete four-arm programme, with all fit states committed before query and outputs committed before grade. One globally frozen programme and fitting recipe across39 sessions; all arm predictions before target access. | Current entrypoint/source closure absent from public task package; prior two-arm execution cannot be inherited. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 16811 bytes; SHA-256 `1dc7041be1d48324c0ae827b1e60a123d4c8d7b0f82469f3a7996d7578e67ace`.
- [Preserved legacy runtime declaration](implementations/registered-runtime/manifest.json)
- [Legacy declaration package](implementations/registered-runtime)

This preserved declaration is lineage, not current execution qualification. Its historical paths may describe the source snapshot.

## Implementation artifacts

- [Registered runtime](implementations/registered-runtime) — Catalog registered source package.
  Scope: This is the source package currently selected by the published catalog; current does not assert executable/scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Source](https://doi.org/10.6084/m9.figshare.9598406)
- [Source](https://github.com/nsteinme/steinmetz-et-al-2019)
- [Source](https://www.nature.com/articles/s41586-019-1787-x)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
