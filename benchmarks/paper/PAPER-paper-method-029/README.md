# Inter-individual and inter-site neural code conversion without shared stimuli

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-029`
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

**Disposition:** source\_unresolved. The original Deeprecon conversion task and author evaluation route are recoverable, but the numeric Figure 2 content-loss baseline and its complete noise-ceiling artifacts have not been recovered and pinned in this review. Raw correlations or a newly rerun local comparator cannot stand in for the published result. Admission also lacks a justified effect, dependence-aware uncertainty and fixed episode budgets.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 28973 bytes; SHA-256 `70a52fc9f86d15d5046c334b96668eae4983a94ed14aadb0aea07f05e6828f9e`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Deeprecon converter inference and complete five-subject/20-directed-pair/six-ROI pattern and profile correlation evaluation for content-loss versus brain-loss converters, with strict optional source noise-ceiling joins. Authentic neural/features/decoder/weight bundle and training lineage, trusted native H5 ingestion, independently accepted ceiling artifacts, matched refitting, figure targets/tolerances, protected improvement data, rights and scientific qualification remain held; fitting converters is outside this evaluator. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Published reference v1](implementations/published-reference-v1) — Reviewed source component.
  Scope: Published Figure 2 reference. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/KamitaniLab/InterSiteNeuralCodeConversion)
- [Code](https://github.com/KamitaniLab/InterSiteNeuralCodeConversion/blob/c264167c2b5a0fa71709a58ae5b50a042f6d7a79/data/files.json)
- [Code](https://raw.githubusercontent.com/KamitaniLab/InterSiteNeuralCodeConversion/c264167c2b5a0fa71709a58ae5b50a042f6d7a79/LICENSE)
- [Code](https://raw.githubusercontent.com/KamitaniLab/InterSiteNeuralCodeConversion/c264167c2b5a0fa71709a58ae5b50a042f6d7a79/README.md)
- [Code](https://www.nature.com/articles/s43588-025-00826-5)
- [Paper](https://www.nature.com/articles/s43588-025-00826-5)
- [Source](https://figshare.com/articles/dataset/17985578)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
