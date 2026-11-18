# Estrogen modulates reward prediction errors and reinforcement learning

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-FIND-046`
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

**Disposition:** ineligible. The registered target is estrous/hormone modulation of dopamine and reward-history associations. The paper explicitly avoids calling the behavioral modulation better or worse because the optimized costs/benefits are unobserved. A greater dopamine contrast or smaller P value cannot surpass that finding; fitting a new predictor would change the task.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 16548 bytes; SHA-256 `380bf31846530f8e60fd7df41d85f02829eae806893478fad252782d8b41dcf1`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Computes source-derived Figure 2 stage contrasts and serum-session dopamine AUC/correlation, retaining full declared rat/session and exclusion ledgers without selecting a cross-archive intersection. Native archive/MAT parity, exact empirical cohorts, singleton MATLAB-axis behavior, Figure 3 RPE/history endpoints, BestFits provenance, protected grouped assessment and scientific qualification remain open; stage associations are observational. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Gain alpha recursion v1](implementations/gain-alpha-recursion-v1) — Reviewed source component.
  Scope: Reviewed additive source component for the existing task. The package documentation and source contracts define its scope; source enrollment does not establish authentic-data execution or scientific qualification.
- [Reward history inputs v1](implementations/reward-history-inputs-v1) — Reviewed source component.
  Scope: Figure 3k reward-history regression inputs. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/constantinoplelab/published/tree/main/EstrousRPEPaper)
- [Paper](https://www.nature.com/articles/s41593-025-02104-z)
- [Source](https://doi.org/10.5281/zenodo.16912311)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
