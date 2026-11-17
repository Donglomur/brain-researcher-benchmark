# Fixed-deadline reaction-time inference from causal EEG

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-003`
- **Track:** Neural-data understanding
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

Finite observed first-response reaction time in seconds after the stimulus, for every admitted at-risk trial; later missing or censored responses have no silently imputed answer.

**Source delivery:** partial\_delivery. The source implements meaningful causal-window, reference and target-last scoring components, but no authenticated native acquisition/event join, complete target producer or runtime exists. Cropping released acausally cleaned512Hz epochs cannot satisfy the revised causal input contract.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_delivered | A future fixed-window32-channel numeric or visual observation with contrast/instruction could be answered without tools. Any view must use only authenticated causal samples through100ms and omit response metadata; no target-informed cropping. | Native causal producer and direct response protocol absent. |
| Typed viewer | not\_delivered | Potential causal EEG-window renderer with identical channel/time support. Typed actions must not reveal future signal, raw acquisition paths or behavioral metadata. | No typed viewer or authenticated causal input route. |
| Tool assisted | not\_delivered | The numerical reference modules can analyze admitted training features, but no participant per-case investigator transport is supplied. Future investigator must share exact inputs/compute and avoid held labels/cross-fold state. | No investigator executor, native data producer or isolation. |
| Frozen program | not\_delivered | Train-only ridge components specify a possible frozen programme; no complete executable episode exists. Freeze full procedure before query; admit raw input and targets independently; reset folds/arms. | No runtime launcher, complete source preparation or protected target producer. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 15791 bytes; SHA-256 `5d064e02e4683758db14701fe5ece6435a36fef125f7a63dc537d0b5b140261c`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Implementation artifacts

- [Causal reaction time](implementations/causal-reaction-time) — Causal reaction time.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Source](https://api.osf.io/v2/files/6822f1def430cf95a9ce9e24/)
- [Source](https://elifesciences.org/articles/108049)
- [Source](https://github.com/GWeindel/decision-times)
- [Source](https://osf.io/j6xuv/)
- [Source](https://raw.githubusercontent.com/GWeindel/decision-times/76464a9ca15564897e58256081af4b99d08ae8db/1-HMP_analyses.ipynb)
- [Source](https://raw.githubusercontent.com/GWeindel/decision-times/76464a9ca15564897e58256081af4b99d08ae8db/data/preprocessing.py)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
