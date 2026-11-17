# Reward-free versus rewarded cortical learning

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-028`
- **Track:** Neural-data understanding
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

Recomputable per-cell d-prime, regional fractions and animal-level before/after contrasts from measured neural arrays; the estimated effect may be null, negative or undefined. Reward-location d-prime is a separate unmatched statistic, not a known reward-coding truth.

**Source delivery:** partial\_delivery. The evaluator computes real neural selectivity, behavioral-common-support contrasts and held-animal residuals from explicit array packets. It neither authenticates native cohorts nor grades participant investigation answers, and reward-location selectivity remains behavior-unmatched. Narrow the current claim to conditional stimulus-selectivity evidence; retain reward analysis as an unresolved companion.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_delivered | Proposed direct interpretation of complete precomputed neural effect tables plus uncertainty could test evidence reading, but that is a separately defined representation. Do not expose evaluator-computed answers while claiming inference from raw observations; freeze what is provided and what must be inferred. | Non-answer-bearing direct observations and independently known response targets. |
| Typed viewer | not\_delivered | Potential typed cell/region/phase plots from permitted arrays; no viewer source exists. Keep observational selection fixed and avoid target-directed outcome filtering. | Viewer, access limits and answer-grading contract. |
| Tool assisted | not\_delivered | Operator-only numerical source is present: Operator analysis backend computes selectivity, common-support contrasts, nulls and held-animal residuals. This does not deliver a participant-facing tool assisted mode. Current evaluator compound packets remain operator-only; a participant needs separate allowed views and no scoring feedback. | Investigator transport, public/private split and submission-claim grader. |
| Frozen program | not\_delivered | Operator-only numerical source is present: Deterministic numerical analysis and frozen before-only explanatory reference. This does not deliver a participant-facing frozen program mode. Fixed preprocessing/threshold/model choices before outcome access; no after-phase fitting or held-mouse leakage. | External programme harness, authentic inputs and qualification. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 20420 bytes; SHA-256 `85ed89b64c56491bfe88bef44a44c34e4119986873f4b6e1fff76fd37b8bf223`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Task implementation.
  Scope: Signal-array stimulus and reward-location selectivity, behavior-standardized contrasts, paired animal uncertainty, trial nulls and a before-only held-animal explanatory reference. Native cohort/session mapping, interpolation and cross-session calibration, the behavior-matched reward endpoint, authentic comparator execution and protected assessment remain held. Scientific qualification is unknown.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Source](https://api.figshare.com/v2/articles/28811129)
- [Source](https://doi.org/10.1038/s41586-025-09180-y)
- [Source](https://github.com/MouseLand/zhong-et-al-2025)
- [Source](https://janelia.figshare.com/articles/dataset/Unsupervised_pretraining_in_biological_neural_network/28811129)
- [Source](https://raw.githubusercontent.com/MouseLand/zhong-et-al-2025/ba64ac697f5d9914926baac79399e80707a5f3a6/LICENSE)
- [Source](https://raw.githubusercontent.com/MouseLand/zhong-et-al-2025/ba64ac697f5d9914926baac79399e80707a5f3a6/README.md)
- [Source](https://raw.githubusercontent.com/MouseLand/zhong-et-al-2025/ba64ac697f5d9914926baac79399e80707a5f3a6/data_process_script.ipynb)
- [Source](https://raw.githubusercontent.com/MouseLand/zhong-et-al-2025/ba64ac697f5d9914926baac79399e80707a5f3a6/utils.py)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
