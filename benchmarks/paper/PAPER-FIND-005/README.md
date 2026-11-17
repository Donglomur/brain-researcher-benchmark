# A brain-wide map of neural activity during complex behaviour

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-FIND-005`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Separate paper outcomes

The current definition supports two independent outcomes: recreate the original findings and exceed them on the same task. Each uses matched paper+data and paper+data+author-code conditions. Contract eligibility and declared protocol availability do not establish a delivered runtime or scientific result.

**Corrected primary scope; outcomes remain unqualified.** Both outcome contracts retain the same primary scientific task. Unresolved source criteria still limit receipt admission.

**Primary goal:** Reproduce and improve the original five-target regional population-decoding result for stimulus side, choice, feedback, wheel speed and wheel velocity, preserving every target's original source cohort, input windows, masks, within-session validation, real/null controls and session/regional summaries. Keep target identities and metrics separate. Improved decoding does not establish unique or causal representation, and original significance is not a superiority rule.

**Primary scientific scope:** The complete original five-target regional population-decoding family in Figures 4a, 5a, 6a and 7a,c, with source controls needed to interpret full session/regional results. Preserve each target's original metric, cohort, window, masks, within-session validation, real/null comparisons and complete eligible effect vector. This is an explicit named selection now, not a historically frozen panel or an all-paper requirement.

**Remaining source limits:**

- Authentic target-specific animal/session/unit/region identities, input masks/windows, complete eligible coverage and exact numerical reference vectors remain unqualified.
- Resolve manuscript versus pinned-source logistic settings without choosing a favorable recipe or silently repairing source.
- Retain the real-score-in-null discrepancy and regional difference-of-medians versus median-of-session-differences branches until original source/version provenance is established.
- The wheel figure-caption metric discrepancy versus Methods/source remains unresolved; binary balanced accuracy and continuous wheel R-squared must not be conflated.
- Independent source replay, trusted output verification, full structured coverage and justified reproduction criteria remain unavailable; source metadata and example predictions do not establish reproduction.
- A defensible paired improvement rule across the complete target/region family with original animal/session dependence remains unavailable. More significant regions, smaller p-values or a new cross-target scalar do not establish superiority.
- Correlated task variables and feedback/consumption confounding limit representation claims. Stronger prediction does not establish unique or causal computation.
- The selected scope preserves original within-session nested validation. New cross-mouse evaluation remains separately named and cannot retroactively replace the paper task.

**Retained source scope:** Other source single-cell, GLM, trajectory and latency results remain separately named empirical evidence, not automatic primary obligations. Original decoder examples and significance/session summaries retain their actual source roles but cannot replace complete effect vectors or serve as superiority tests. Cross-mouse evaluation is a prospective extension, not a substitute for the selected within-session result. Preserve all useful source components within these limits.

- [Reviewed primary scope correction](../../../docs/provenance/paper-outcome-scope-decisions.v1.json)
- [Original-finding reproduction contract](reproduction.v2.json)
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

**Disposition:** source\_unresolved. The broad regional representation registration includes genuine original decoding endpoints. However, the reviewed paper/code do not establish the exact original regional score vector and complete cohort/scoring manifest needed for a paper comparison. The local single-cell significance/fraction evaluator cannot substitute for source population decoding. A new cross-mouse split or pooled scalar would be an extension.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 19502 bytes; SHA-256 `9b29d44889a88bed9203438395999d5a01c27ac6deac9e47ffc1fa94cc22b991`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)
- [Pre-scope reproduction source role](docs/provenance/reproduction.pre-scope.role.json)
- [Preserved pre-scope reproduction declaration](docs/provenance/reproduction.pre-scope.v1.json)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Sorted spikes and versioned trial exports to stimulus/choice/feedback single-cell sensitivity, common source masks, regional dual-test fractions and separate mouse-weighted summaries. Native IBL cohort/unit UUID/QC reconciliation, full regional manifest, paper-versus-example choice-window adjudication, authentic numerical agreement, protected references and scientific qualification remain held. Population decoding, trajectories, GLM and whole-atlas reproduction are outside this component. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Decoder score import v1](implementations/decoder-score-import-v1) — Reviewed source component.
  Scope: Original decoding score import. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/int-brain-lab/paper-brain-wide-map)
- [Paper](https://www.nature.com/articles/s41586-025-09235-0)
- [Source](https://int-brain-lab.github.io/iblenv/notebooks_external/data_release_brainwidemap.html)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
