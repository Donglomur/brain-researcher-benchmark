# Perturbing human V1 degrades the fidelity of visual working memory

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-signal-add-021`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Ineligible
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
| Improvement | Paper data | ineligible | unresolved | unresolved | Unknown |
| Improvement | Paper data author code | ineligible | unresolved | unresolved | Unknown |

Author-baseline replay and historical reconstruction attempts retain their original scopes. They are not promoted to qualified AI reproductions or improvements by these contracts.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** ineligible. The source tests a causal perturbation effect on behavior and EEG. Increasing an effect or its significance does not improve a prediction or estimator against known truth. Existing fixed-region and behavioral scorers reproduce specified summaries; selecting different windows or exclusions cannot become a same-task paper victory.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Recorded public evidence

Each record keeps the scope of its original report. It is not current runtime qualification.

- [Paper calibration attempt — paper\_data\_shared\_method](../../../docs/science/difficulty-pilot-20261117.json): Complete accepted fixed-region derivative: 12 regions, 36 effects and 540 leave-one-out summaries; not the original primary cluster analysis.
- [Paper calibration attempt — paper\_data\_shared\_method\_official\_code](../../../docs/science/difficulty-pilot-20261117.json): Complete accepted fixed-region derivative: 12 regions, 36 effects and 540 leave-one-out summaries; not the original primary cluster analysis.
- [Historical paper calibration](../../../docs/provenance/execution/historical-evidence-v1/profiles.json): 15 participants in 14,061 processed rows; 135 participant-condition means/counts, nine summaries, five spatial and six timing/provenance comparisons.

Inspect conditions, metrics and limits with `python3 scripts/neurobench.py evidence PAPER-paper-signal-add-021`. Programme evidence does not establish direct interpretation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 13798 bytes; SHA-256 `4d2850a2312ab3468eaa8db79d32989ec1be8ebb09d9d488cac4d8a0601ee60a`.
- [Preserved legacy runtime declaration](implementations/registered-runtime/manifest.json)
- [Legacy declaration package](implementations/registered-runtime)

This preserved declaration is lineage, not current execution qualification. Its historical paths may describe the source snapshot.

## Implementation artifacts

- [Registered runtime](implementations/registered-runtime) — Calibration only.
  Scope: This is the source package currently selected by the published catalog; current does not assert executable/scientific qualification. This retained scoring facade requires 2 source or input dependencies absent from the public baseline. Correcting its repository locator does not make it runnable from this checkout alone. This limit does not apply automatically to sibling implementations of the task. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Tms figure2b construction v1](implementations/tms-figure2b-construction-v1) — Calibration only.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Tms independent condition portable profile v1](implementations/tms-independent-condition-portable-profile-v1) — Calibration only.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Fixed region artifacts](implementations/fixed-region-artifacts) — Calibration only.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Fixed region reference](implementations/fixed-region-reference) — Calibration only.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Behavioral reference](implementations/behavioral-reference) — Calibration only.
  Scope: Package README explicitly identifies evaluator task PAPER-paper-signal-add-021; preserve four-file component. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/clayspacelab/Dake_Curtis_TMSV1_2025)
- [Paper](https://www.nature.com/articles/s41467-025-57882-8)
- [Source](https://osf.io/hf5a4/)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
