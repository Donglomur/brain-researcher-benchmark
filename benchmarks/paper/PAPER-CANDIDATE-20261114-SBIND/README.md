# Joint behavioral decoding and neural prediction from full spatial imaging fields

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-CANDIDATE-20261114-SBIND`
- **Track:** Paper research
- **Registration:** Expansion draft
- **Declared specification status:** Design ready
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
| Improvement | Paper data | design\_ready | unresolved | unresolved | Unknown |
| Improvement | Paper data author code | design\_ready | unresolved | unresolved | Unknown |

Author-baseline replay and historical reconstruction attempts retain their original scopes. They are not promoted to qualified AI reproductions or improvements by these contracts.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** design\_ready. The paper provides ordered behavioral and neural prediction results for both complete widefield assays and thirteen fUS sessions, including numerical Table 2–3 SBIND baselines. Exact data identities, published folds/preprocessing replay, full evaluator and a justified joint decision rule remain incomplete; no execution readiness or improvement is claimed.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 11818 bytes; SHA-256 `c4982ed2ccc0272e6023300cc50bc008e81bfbbe14a72c1a786af66254d1e9a9`.
- [Registration and provenance](../../../docs/provenance/registrations/expansion-20261114-v11/registry.json)

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Implementation artifacts

- [Continuous normalization](implementations/continuous-normalization) — Calibration only.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Whole trial preparation](implementations/whole-trial-preparation) — Calibration only.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Endpoint kernels](implementations/endpoint-kernels) — Reviewed source component.
  Scope: SBIND endpoint arithmetic. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/ShanechiLab/SBIND)
- [Data](https://data.caltech.edu/records/pa710-cdn95)
- [Data](https://repository.cshl.edu/id/eprint/38599/)
- [Paper](https://proceedings.mlr.press/v267/hosseini25a.html)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
