# Cross-session transfer of a unified neural population decoder

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-CANDIDATE-20261114-POYO`
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

**Disposition:** source\_unresolved. Published POYO transfer results are identified, but the historical corpus, complete original adaptation grid and exact scoring provenance are not bound to the registered prospective macro-session endpoint. The contemporary frozen-grid consumer cannot establish 2023 task equivalence.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 16401 bytes; SHA-256 `4343a6ae842820e30a7513cb032b86dffb54b6afa21f431c120940fbe6ff82a1`.
- [Registration and provenance](../../../docs/provenance/registrations/expansion-20261114-v11/registry.json)

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Published transfer panel provenance](docs/provenance/published-transfer-panel.v1.json)
- [Published transfer panel scope](docs/provenance/published-transfer-panel.v1.md)
- [Contemporary code/import lineage; original2023 result linkage unresolved (identity map)](docs/provenance/code-import-lineage.v1.json)
- [Contemporary code/import lineage; original2023 result linkage unresolved](docs/provenance/code-import-lineage.v1.md)

## Implementation artifacts

- [Frozen grid evaluator](implementations/frozen-grid-evaluator) — Calibration only.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Author label correspondence v1](implementations/author-label-correspondence-v1) — Reviewed source component.
  Scope: 158 ordered author-project source-label correspondences only, preserving 100 literal labels and 58 suffix relations. No physical-session/subject/train-test/checkpoint/score qualification. Public fixture-free harness and README projection have a separate static portability inspection.
- [Protected grid evaluator](implementations/protected-grid-evaluator) — Reviewed source component.
  Scope: Protected POYO adaptation grid. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/nerdslab/poyo)
- [Data](https://dandiarchive.org/dandiset/000070/0.260528.0919)
- [Data](https://dandiarchive.org/dandiset/000688/0.250122.1735)
- [Data](https://portal.nersc.gov/project/crcns/download/dream/data_sets/Flint_2012)
- [Data](https://zenodo.org/records/583331)
- [Paper](https://papers.nips.cc/paper_files/paper/2023/hash/8ca113d122584f12a6727341aaf58887-Abstract-Conference.html)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
