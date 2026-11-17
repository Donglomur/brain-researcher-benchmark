# Fine reach-kinematics decoding from calcium

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-025`
- **Track:** Neural-data understanding
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

The 24 ordered measured jointAngles trajectories in degrees OR the 24 jointVelocities trajectories in degrees/second, scored in separate requests; they are not a single 48-channel endpoint.

**Source delivery:** partial\_delivery. The complete five-mouse/ten-session normalized-data decoder and measured-target scorer exist. Authentic native extraction, trial eligibility, clock/ROI alignment and protected participant delivery remain unverified; use the declared retrospective session-local endpoint, not an author-reproduction or cross-animal-transfer claim.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_delivered | Proposed numeric calcium matrices and fixed lift grid could support direct complete-trajectory answers; no no-tools context/collector is supplied. Only public calibration labels and query neural/context values; hold all evaluation kinematics private. | Complete no-tools observation and response protocol. |
| Typed viewer | not\_delivered | A source-faithful trace/raster viewer could expose 100-ROI calcium windows; none is supplied. Typed trace selection/rendering must preserve fixed observations without returning target trajectories. | Renderer, restricted action schema and matched numerical observation budget. |
| Tool assisted | not\_delivered | Numerical fit/score functions are operator APIs; a case-adaptive investigator transport is not supplied. Proposed equal data, tool/checkpoint and compute access with no private compound scoring request. | Per-case tool transport and independently protected scorer. |
| Frozen program | not\_delivered | Operator-only numerical source is present: Training-only numerical decoder and complete external-prediction scoring API. This does not deliver a participant-facing frozen program mode. Freeze recipe, eligibility and observation support before evaluation; candidate receives training labels and query neural values only. | Candidate runner and authentic-input/protected-execution qualification. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 29280 bytes; SHA-256 `6c3261c1883d99e6e4207302f6218ba403d578076889c33c4e9d797195487bb3`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Prospective calcium/kinematics decoder and controls](docs/train-only-decoding-v1.md)

## Implementation artifacts

- [Train only decoding v1](implementations/train-only-decoding-v1) — Task implementation.
  Scope: Complete admitted normalized five-mouse/ten-session calcium and kinematics decoder, scorer and controls with prospective training-only decoder semantics and session-local calibration. Authentic MAT/eligibility/clock identity, upstream exposure and fold safety, source-reference parity and competence, protected execution and scientific qualification remain unverified. Local new-mouse calibration is not cross-animal transfer; five-mouse uncertainty is descriptive.
- [Participant delivery v1](implementations/participant-delivery-v1) — Reviewed source component.
  Scope: Participant delivery for NEURAL-025. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Source](https://api.figshare.com/v2/articles/28326998)
- [Source](https://doi.org/10.7554/eLife.106270.3)
- [Source](https://figshare.com/articles/dataset/Data_from_Mouse_sensorimotor_cortex_reflects_complex_kinematic_details_during_reaching_and_grasping_eLife_2025/28326998)
- [Source](https://github.com/kaufmanlab/GSK26-public)
- [Source](https://raw.githubusercontent.com/kaufmanlab/GSK26-public/815b610b3beddfed5a3abf611d3a465ab9e4ce5c/LICENSE)
- [Source](https://raw.githubusercontent.com/kaufmanlab/GSK26-public/815b610b3beddfed5a3abf611d3a465ab9e4ce5c/README.md)
- [Source](https://raw.githubusercontent.com/kaufmanlab/GSK26-public/815b610b3beddfed5a3abf611d3a465ab9e4ce5c/docs/QUICK_REFERENCE.md)
- [Source](https://raw.githubusercontent.com/kaufmanlab/GSK26-public/815b610b3beddfed5a3abf611d3a465ab9e4ce5c/docs/SUMMARY.md)
- [Source](https://raw.githubusercontent.com/kaufmanlab/GSK26-public/815b610b3beddfed5a3abf611d3a465ab9e4ce5c/main/fig5/analysis/decode.m)
- [Source](https://raw.githubusercontent.com/kaufmanlab/GSK26-public/815b610b3beddfed5a3abf611d3a465ab9e4ce5c/preproc/eventLockData.m)
- [Source](https://raw.githubusercontent.com/kaufmanlab/GSK26-public/815b610b3beddfed5a3abf611d3a465ab9e4ce5c/preproc/loadLock4Decode.m)
- [Source](https://raw.githubusercontent.com/kaufmanlab/GSK26-public/815b610b3beddfed5a3abf611d3a465ab9e4ce5c/utils/loadData.m)
- [Source](https://www.biorxiv.org/content/10.1101/2025.02.19.639049v1)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
