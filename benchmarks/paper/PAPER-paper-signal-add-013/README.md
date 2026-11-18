# BOLD signal changes can oppose oxygen metabolism across the human cortex

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-signal-add-013`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Separate paper outcomes

The current definition supports two independent outcomes: recreate the original findings and exceed them on the same task. Each uses matched paper+data and paper+data+author-code conditions. Contract eligibility and declared protocol availability do not establish a delivered runtime or scientific result.

**Corrected primary scope; outcomes remain unqualified.** Both outcome contracts retain the same primary scientific task. Unresolved source criteria still limit receipt admission.

**Primary goal:** Reproduce the original Figure5 fitted-estimation result: baseline CMRO2 from OEF, CBF and CBV, and task-related deltaCMRO2 from deltaOEF and deltaCBF, separately in the source concordant and discordant voxel strata. Preserve all four models, original participant/voxel support, physiological-map and mask lineage, centering and source fit outputs. Retain the paper's other physiological findings as separately named evidence; fitted agreement does not establish independent physiological accuracy. Assess improvement only if a meaningful same-result criterion beyond fitting the Fick-derived target can be justified.

**Primary scientific scope:** The explicitly root-authorized and independently scientifically reviewed Figure 5 fitted-estimation revision: two baseline and two task-change models in concordant/discordant strata, each with original coefficients/intercepts, fit statistics, degrees of freedom, significance and contribution interpretation. Preserve original participant/task/voxel rows, source masks and repeated-row weighting, physiological target/predictor calibration and map lineage, eligibility, thresholding and centering. This is an empirical fitted-model result, not held-out or independent-metabolism prediction. The older physiology registration does not supersede the reviewed named-result revision.

**Remaining source limits:**

- Paper task-change support specifies CALC medians over 40 and MEM over 30 participants, whereas original code uses first30 for both; this source-parity conflict remains unresolved.
- Exact participant/voxel identities, significant-task/concordance masks, corrected/original/semiquantitative map lineage, source row concatenation and exclusion/centering support remain unqualified.
- All four native fits, contribution/statistic definitions and numeric reproduction criteria still require independent authentication.
- CMRO2 targets derive from physiological predictor maps via Fick's principle. Larger fitted R-squared, direct identity evaluation or extra model flexibility cannot by themselves earn physiological-improvement credit.
- Meaningful same-result superiority, dependence-aware family decisions, paired access/resource manifests and independent submitted-computation verification remain unavailable. Reproduction is a separate first-class outcome and need not depend on improvement being admissible.
- No all-Figures-2-4 or complete-Figure-5b/c expansion is authorized merely by source authenticity or preservation language; no external QSM map is treated as independent CMRO2 ground truth.

**Retained source scope:** partial\_primary\_coverage: The accepted two-baseline-cell component covers only part of the selected four-model primary; original task-change fits remain required. separate\_empirical\_results\_and\_safeguards: Complete Figure 2 regional/task effects, Figure 3 prevalence/spatial/amplitude/Davis-model comparisons, Figure 4 mixed-voxel consistency and Figure 5b/c physiological/external-QSM conclusions remain separately named evidence. Their consumed masks/map definitions remain required dependencies, but their full numerical outcome envelopes are not automatic grading requirements. legacy\_calibration: The existing CALC-control map reduction remains useful calibration for the prior descriptive scope, not a substitute for Figure 5 fits. prospective\_extension\_or\_outside\_registered\_computation: New participant/voxel holdouts, independent oxygen-metabolism prediction, raw-to-map reconstruction, control18 and replication10 execution are not silently added to the selected fitted-estimation task.

**Retained source roles:**

| Source field | Declared role |
| --- | --- |
| Item 1 / Role | Partial primary coverage |
| Item 1 / Scope | The accepted two baseline cell component covers only part of the selected four model primary; original task change fits remain required. |
| Item 2 / Role | Separate empirical results and safeguards |
| Item 2 / Scope | Complete Figure 2 regional/task effects, Figure 3 prevalence/spatial/amplitude/Davis model comparisons, Figure 4 mixed voxel consistency and Figure 5b/c physiological/external QSM conclusions remain separately named evidence. Their consumed masks/map definitions remain required dependencies, but their full numerical outcome envelopes are not automatic grading requirements. |
| Item 3 / Role | Legacy calibration |
| Item 3 / Scope | The existing CALC control map reduction remains useful calibration for the prior descriptive scope, not a substitute for Figure 5 fits. |
| Item 4 / Role | Prospective extension or outside registered computation |
| Item 4 / Scope | New participant/voxel holdouts, independent oxygen metabolism prediction, raw to map reconstruction, control18 and replication10 execution are not silently added to the selected fitted estimation task. |

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

**Disposition:** source\_unresolved. Source Figure 5 contains an ordered regression-estimation route: CMRO2 and its task changes are fitted from source hemodynamic inputs with reported stratum-specific R-squared values. This source-native subtask can be investigated independently of the legacy descriptive CALC–CTRL endpoint. Exact native row/mask/model binding and a scientifically valid improvement criterion remain unresolved: CMRO2 is itself derived from these inputs through Fick’s principle, so increasing fitted R-squared may only reconstruct a known identity and cannot by itself establish better physiological estimation.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 24101 bytes; SHA-256 `7c0c9aeec7eab30eef70288c733d602f420f486ff40c8e3a0f315a8b67e861ee`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)
- [Pre-scope reproduction source role](docs/provenance/reproduction.pre-scope.role.json)
- [Preserved pre-scope reproduction declaration](docs/provenance/reproduction.pre-scope.v1.json)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Computes the fixed 40-participant CALC-CTRL map contrast, corrected primary and explicitly mixed-lineage original sensitivity, distinct source median reductions and descriptive paired-participant summaries. Authentic maps/masks/geometry, physiological correction, native PLS, figure parity, geometry-preserving spatial nulls, protected references and scientific qualification remain held; data CC0 and upstream code CC BY-NC-SA 4.0 terms remain distinct. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Figure5 relative importance v1](implementations/figure5-relative-importance-v1) — Reviewed source component.
  Scope: Reviewed additive source component for the existing task. The package documentation and source contracts define its scope; source enrollment does not establish authentic-data execution or scientific qualification.
- [Figure5 baseline v1](implementations/figure5-baseline-v1) — Reviewed source component.
  Scope: Figure 5 baseline regressions. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/NeuroenergeticsLab/two_modes_of_hemodynamics)
- [Paper](https://www.nature.com/articles/s41593-025-02132-9)
- [Source](https://openneuro.org/datasets/ds004873/versions/2.0.6)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
