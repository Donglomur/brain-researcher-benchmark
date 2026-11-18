# Locate the nonlinear mapping responsible for behaviorally relevant reaching dynamics

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-CANDIDATE-20261114-DPAD`
- **Track:** Paper research
- **Registration:** Expansion draft
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

**Disposition:** source\_unresolved. Figure 6h-i supplies an ordered neural/behavior prediction task, but this review did not recover its numeric author results or exact random electrode subset. The local candidate session roster and independently implemented scorer do not establish an identical source-paper comparison. The registered held-session and causal-filter proposals are extensions, not paper victory.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 11008 bytes; SHA-256 `e0876b9ab434fc946a46f93cd0d1883a0c9306d1a1c45fe0560291126faf057c`.
- [Registration and provenance](../../../docs/provenance/registrations/expansion-20261114-v11/registry.json)

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: DPAD Figure 6h–i prediction-evaluation component: training-only architecture/dimension selection followed by complete candidate seven-session/fold/dimension nonlinear-locus correlations, paired summaries and the neural/behavior frontier. Exact session/electrode mapping, publication-era native configurations and preprocessing, actual DPAD fitting/prediction provenance, protected references/access parity, rights and scientific reproduction remain held; temporal-fold results are not held-session improvement. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Paired candidate v2](implementations/paired-candidate-v2) — Reviewed source component.
  Scope: DPAD paired candidate scorer. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/ShanechiLab/DPAD)
- [Data](https://zenodo.org/records/3854034)
- [Paper](https://www.nature.com/articles/s41593-024-01731-2)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
