# Incremental contemporaneous movement information in motor gamma

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-050`
- **Track:** Neural-data understanding
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

Independently computed paired difference in held-out movement MSE between state/time baseline and gamma-augmented prediction; positive, null and negative increments are all valid. Matched high-minus-low movement gamma contrasts are secondary.

**Source delivery:** partial\_delivery. The initial evaluator implements bounded-array gamma preparation, held-patient/held-day ridge comparisons and matched-event diagnostics. Authentic NWB extraction, anatomy/pose/clock qualification and complete cohort remain open. Its endpoint is same-window wrist speed, not future movement forecasting.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_suitable | The target is an across-patient matched prediction increment requiring held-out model fitting and aggregation. Reading isolated waveform images cannot establish this estimand; a direct single-window movement decoder would be a separately specified condition. | No direct-observation task or direct-response protocol for this aggregate contrast. |
| Typed viewer | not\_delivered | A future ECoG/spectrum viewer could support artifact and matched-window investigation. Only permitted observation projections; target-derived matching remains operator-only and cannot leak query speed to a prediction actor. | No typed-viewer implementation or complete participant transport. |
| Tool assisted | not\_delivered | Numerical prepare/evaluate routines support an operator investigation and reproducible conditional-contrast calculation. Per-case participants would need protected source/target roles, matched tools and sealed fitting access; current operator CLI does not provide that isolation. | Participant case harness and independent authentic execution evidence.; Operator analysis/comparator source does not supply a participant episode or candidate programme execution route. |
| Frozen program | not\_delivered | The fixed evaluation programme implements a predeclared gamma feature and ridge comparison. Keep protocol, folds, anatomy and QC frozen before authentic outcomes; this supplied comparator is not an arbitrary candidate runner. | Arbitrary candidate execution/admission and genuine full-source qualification.; Operator analysis/comparator source does not supply a participant episode or candidate programme execution route. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 16880 bytes; SHA-256 `e4b3fba7d778c9fce19dc73fcd682999aa3106b6ea3da6a2d82d11b9498ac432`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Task implementation.
  Scope: Bounded exported ECoG/pose arrays to prospective gamma features, grouped state/time versus gamma movement prediction, matched-event contrasts, patient/day summaries and temporal-shift diagnostics. Authentic NWB conversion, complete source population, anatomy/laterality and pose scale, stream alignment and artifact QC, frozen protocol/resources, protected targets and scientifically competent reference runs remain unqualified.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Source](https://api.dandiarchive.org/api/dandisets/000055/versions/0.220127.0436/)
- [Source](https://dandiarchive.org/dandiset/000055)
- [Source](https://doi.org/10.1038/s41597-022-01280-y)
- [Source](https://github.com/BruntonUWBio/ajile12-nwb-data)
- [Source](https://raw.githubusercontent.com/BruntonUWBio/ajile12-nwb-data/f44ca6f6c51251b62b6f47492bba400472d4a7ba/Example_AJILE12_exploratory_analysis.ipynb)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
