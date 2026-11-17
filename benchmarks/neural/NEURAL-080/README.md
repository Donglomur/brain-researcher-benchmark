# Video dynamics versus eye movements in EEG

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-080`
- **Track:** Neural-data understanding
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

Complete held original-unit EEG response arrays for each person/video case. The participant submits predicted responses; their risk and improvement over the fixed FULL decoder depend on those predictions. The nuisance\_eye-minus-full contrast is an operator-computed reference diagnostic, not a participant answer or score.

**Source delivery:** partial\_delivery. The actual source advances beyond the historical specification with a genuine controlled held-person/family target, but remains an inactive, empirically unqualified checkpoint. Preserve the older diagnostic as a distinct scope.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_suitable | The endpoint requires predicted hidden EEG and a controlled multi-arm risk contrast over cohort/stimulus support. Showing query EEG would reveal the answer; a small waveform inspection would change the estimand. | No direct observation assay for this controlled encoding contrast. |
| Typed viewer | not\_suitable | A neural-target viewer cannot remain an input to hidden-response prediction. Any future exploratory plot is separate evidence and cannot replace the fixed complete-array comparator. | No typed viewer condition delivered for this endpoint. |
| Tool assisted | not\_delivered | The campaign declares per-case adaptive/tool-regime conditions but only launches a preselected arbitrary candidate\_entry with a mode argument. It supplies no participant provider/action/tool loop to implement interactive investigation. A case\_adaptive label and shared process limits do not establish a delivered adaptive participant. Any future actor must preserve the same allowed outerTRAIN/innerVALIDATION support, budgets, no query targets/transforms and fresh case state. | Concrete participant adaptive actor and tool/action controller bound to the complete case contract.; Authentic input, native transport and enforced isolation qualification. |
| Frozen program | source\_available | campaign.execute and runner.run\_case provide concrete source for invoking an externally supplied preselected programme on every pinned case and capturing its complete response array; the solver programme itself is an input. Freeze before outer query access and grade all complete response arrays; source declarations do not qualify runtime. | Complete native reference/candidate execution and independent qualification. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 21047 bytes; SHA-256 `7732e5cc30d64f016f9dac08b0c7d0ccd5d5f3e1643f3c439d68f7a8b68fafad`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Implementation artifacts

- [Neural 080](implementations/neural-080) — Task implementation source.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Source](https://arxiv.org/abs/2608.28768)
- [Source](https://github.com/OpenNeuroDatasets/ds008257)
- [Source](https://github.com/gifale95/EMD)
- [Source](https://openneuro.org/datasets/ds008257)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
