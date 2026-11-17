# Repeated-image EEG identification

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-055`
- **Track:** Neural-data understanding
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

A private bijection between200 opaque EEG query IDs and200 candidate-image IDs within each held-person panel.

**Source delivery:** partial\_delivery. Public source implements a ten-person,200-candidate batch retrieval study with complete independent/programme/investigator comparisons. Authentic packets, numerical parity, execution containment and all30 scientific gates remain unqualified; source inspection is available but no current model result follows.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_delivered | No-tools reading of compact EEG traces or candidate displays is not a current condition. Current batch arrays and training/image models are tool/programme observations. | Define faithful no-tools information view and independent response collector. |
| Typed viewer | not\_delivered | No typed EEG/candidate-image viewer is supplied. A viewer must preserve80-repeat representation and fixed candidate priors while hiding query associations. | Audited viewer transport and complete-panel answer collection. |
| Tool assisted | source\_available | I: bounded online investigator decisions over authorized full-batch data/tools. Fresh same-cell context; only sealed action set; no new query fitting; full costs/failed operations retained. | Actual semantic/native/resource qualification. |
| Frozen program | source\_available | F: one precommitted numerical learning/search policy and sealed state. No investigator decisions or generated analysis policy in F; fixed scientific predictor calls permitted only in their declared role. | Full authentic execution and reference qualification. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 15049 bytes; SHA-256 `2b8db9ada2710eb289fcfb98ef709cecd41598ce3d969c2eb3f0e261e905e5e7`.
- [Preserved legacy runtime declaration](implementations/registered-runtime/manifest.json)
- [Legacy declaration package](implementations/registered-runtime)

This preserved declaration is lineage, not current execution qualification. Its historical paths may describe the source snapshot.

## Implementation artifacts

- [Registered runtime](implementations/registered-runtime) — Catalog registered source package.
  Scope: This is the source package currently selected by the published catalog; current does not assert executable/scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Source](https://api.osf.io/v2/licenses/563c1cf88c5e4a3877f9e96a/)
- [Source](https://api.osf.io/v2/nodes/anp5v/files/osfstorage/)
- [Source](https://api.osf.io/v2/nodes/y63gw/files/osfstorage/)
- [Source](https://doi.org/10.1016/j.neuroimage.2022.119754)
- [Source](https://github.com/gifale95/eeg_encoding)
- [Source](https://osf.io/3jk45/)
- [Source](https://raw.githubusercontent.com/gifale95/eeg_encoding/101997d4f14c41b615bcaf8c0907740106d260c5/04_synthesizing_eeg_data/linearizing_encoding_utils.py)
- [Source](https://raw.githubusercontent.com/gifale95/eeg_encoding/101997d4f14c41b615bcaf8c0907740106d260c5/LICENSE.md)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
