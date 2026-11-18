# Separating cognitive and motor processes in the behaving mouse

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-FIND-025`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Separate paper outcomes

The current definition supports two independent outcomes: recreate the original findings and exceed them on the same task. Each uses matched paper+data and paper+data+author-code conditions. Contract eligibility and declared protocol availability do not establish a delivered runtime or scientific result.

- [Original-finding reproduction contract](reproduction.v1.json)
- [Paired outcome protocols](outcomes.v1.json)
- [Preserved definition before dual outcomes](historical/task.pre-outcomes.v1.json)

| Outcome | Information condition | Endpoint eligibility | Protocol status | Declared availability | Scientific outcome |
| --- | --- | --- | --- | --- | --- |
| Reproduction | Paper data | source\_unresolved | unresolved | unresolved | Unknown |
| Reproduction | Paper data author code | source\_unresolved | unresolved | unresolved | Unknown |
| Improvement | Paper data | source\_unresolved | unresolved | unresolved | Unknown |
| Improvement | Paper data author code | source\_unresolved | unresolved | unresolved | Unknown |

Author-baseline replay and historical reconstruction attempts retain their original scopes. They are not promoted to qualified AI reproductions or improvements by these contracts.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. The paper includes ordered decoding and movement-prediction analyses, but final-paper versus author-code metric, cohort and fitting identities remain unresolved. The existing protected signed-VE protocol is prospective; it must not replace the original paper endpoint or convert a residual cognitive finding into a performance win.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 66873 bytes; SHA-256 `5214d92a2a3dee1f2113650d232bc0ddd26d5f5d29b0a809a3e59ab9e6bc7470`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Implementation artifacts

- [Submission comparison](implementations/submission-comparison) — Calibration only.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Normalized variance v1](implementations/normalized-variance-v1) — Reviewed source component.
  Scope: Selected inactive source component for the existing task. The package documentation and source contracts define its retained scope; runtime admission and scientific qualification remain separate.
- [Artifact evaluator v1](implementations/artifact-evaluator-v1) — Reviewed source component.
  Scope: FIND025 artifact evaluator, version 1. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/economolab/subspaceID)
- [Paper](https://www.nature.com/articles/s41593-024-01859-1)
- [Source](https://doi.org/10.5281/zenodo.13941414)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
