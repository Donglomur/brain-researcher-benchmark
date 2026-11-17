# SMC-RNN: reproduce source findings and exceed the original offline MC\_Maze 20-ms endpoint

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-SMC-RNN-2024`
- **Track:** Paper research
- **Registration:** Expansion draft
- **Declared specification status:** Design ready
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Separate paper outcomes

The current definition supports two independent outcomes: recreate the original findings and exceed them on the same task. Each uses matched paper+data and paper+data+author-code conditions. Contract eligibility and declared protocol availability do not establish a delivered runtime or scientific result.

### Current primary improvement policy

**Disposition:** design\_ready.

The candidate source interface accepts one complete offline prediction set over the full 35-bin panel. Source selectors do not authenticate an episode policy, source comparator, execution or scientific outcome.

- [Selected current improvement contract](improvement.temporal-scope.v1.json)
- [Authenticated policy revision](primary-successor.v1.json)
- [Current scientific contract](docs/scientific-contract.temporal-scope.v1.json)
- [Reviewed task projection](docs/temporal-scope-projection.v1.json)

| Candidate source | Selector |
| --- | --- |
| Delivery | [delivery.py](implementations/offline-nlb-outcomes-v1/delivery.py) |
| Scorer | [scorer.py](implementations/offline-nlb-outcomes-v1/scorer.py) |
| Policy | [policy.py](implementations/offline-nlb-outcomes-v1/policy.py) |

### Retained author-source reproduction routes

Both author recipes remain available as source routes: causal-proposal, noncausal-proposal. Author calibration is not a qualified submitted AI reproduction; source-matched receipts cannot be relabeled as offline candidate receipts.

| Author source | Selector |
| --- | --- |
| Delivery | [delivery.py](implementations/source-matched-nlb-v1/delivery.py) |
| Scorer | [scorer.py](implementations/source-matched-nlb-v1/scorer.py) |
| Protocol | [protocol.json](implementations/source-matched-nlb-v1/protocol.json) |

Both source routes remain scientifically unknown; these selectors do not authorize execution.

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

## Retained author-source policy

This original registration contract remains attached to the author-source reproduction and calibration routes. The selected current policy above defines the offline candidate interface; the retained author restrictions do not govern that candidate.

**Disposition:** design\_ready. The complete original endpoint, author code/checkpoints and original scorer are recovered. Source preparation and qualification have executable routes; no full author score match, candidate superiority or final admission policy is established.

- [Retained original improvement contract](improvement.v1.json)
- [Initial source-paper task registration (no predecessor)](../../../docs/provenance/registrations/paper-initial/PAPER-SMC-RNN-2024.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Recorded public evidence

Each record keeps the scope of its original report. It is not current runtime qualification.

- [Author model inference probe](docs/native-cost-characterization.json): Actual selected author-checkpoint inference on the first train and eval chunks only; no complete predictions, scores or 32-repeat baseline.
- [Author model inference probe](docs/native-cost-characterization.json): Actual selected author-checkpoint inference on the first train and eval chunks only; no complete predictions, scores or 32-repeat baseline.
- [Paper source preparation](docs/source-preparation-evidence.json): Complete original MC\_Maze 20ms input preparation and paired participant materials, with generated source/scorer controls. This report excludes separately recorded author-model timing and all scientific performance evaluation.

Inspect conditions, metrics and limits with `python3 scripts/neurobench.py evidence PAPER-SMC-RNN-2024`. Programme evidence does not establish direct interpretation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 12119 bytes; SHA-256 `b88feedacaa4cda6de9a1a3c012c29c5a6a1e48dff92b16e68d0fc1dc130020d`.
- [Registration and provenance](../../../docs/provenance/registrations/paper-initial/PAPER-SMC-RNN-2024.json)

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Original two-arm scientific comparison and scope](docs/scientific-contract.json)
- [Source preparation and paired-export engineering evidence](docs/source-preparation-evidence.json)
- [Partial native execution and full-run cost estimates](docs/native-cost-characterization.json)

## Implementation artifacts

- [Offline nlb outcomes v1](implementations/offline-nlb-outcomes-v1) — Offline whole trial outcome policy delivery and scoring source.
  Scope: Reviewed source for the offline whole-trial NLB outcome successor, including policy, delivery, scoring and generated controls. It reuses retained source-matched scorer, delivery and protocol dependencies. Registration does not activate a runtime or qualify reproduction or improvement; trusted episode policy, authentic execution, receipt provenance and numerical scientific outcomes remain separately required and unestablished. Existing task definitions, histories and retained source artifacts are preserved.
- [Source matched nlb v1](implementations/source-matched-nlb-v1) — Original panel preparation, paired materials and frozen prediction scoring.
  Scope: Source-matched MC\_Maze 20-ms preparation and paired paper/data versus paper/data/official-code exports, selected author-checkpoint inference and frozen-prediction scoring for both original proposal arms with all companion metrics. Complete author-score calibration, equal participant budgets, joint superiority admission and scientific qualification remain unestablished. Source delivery and engineering controls are not solver performance; original targets are publicly exposed.
- [Paired reproduction v1](implementations/paired-reproduction-v1) — Joint original source method reproduction evaluation.
  Scope: Joint freeze and scoring interface for two complete original-method prediction sets and all eight source findings through the unchanged evaluator. This source component does not supply an agreement policy, establish original-method execution or qualify AI reproduction, historical source linkage, candidate isolation or scientific performance.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/mackelab/smc_rnns)
- [Paper](https://papers.neurips.cc/paper_files/paper/2024/file/209423f076b6479ab3a4f45886e30306-Paper-Conference.pdf)
- [Source](https://doi.org/10.48324/dandi.000128/0.220113.0400)
- [Source](https://github.com/mackelab/smc_rnns)
- [Source](https://papers.neurips.cc/paper_files/paper/2024/file/209423f076b6479ab3a4f45886e30306-Paper-Conference.pdf)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
