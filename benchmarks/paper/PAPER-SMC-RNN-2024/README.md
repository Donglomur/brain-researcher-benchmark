# SMC-RNN: reproduce source findings and exceed the original offline MC\_Maze 20-ms endpoint

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-SMC-RNN-2024`
- **Track:** Paper research
- **Registration:** Expansion draft
- **Declared specification status:** Design ready
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Separate paper outcomes

Both first-class outcomes use continuous fixed-panel measurements under the same typed policy. Reproduction reports both original source methods and all eight findings; improvement reports one complete offline four-metric vector with separate reference differences. No binary reproduction or improvement pass is assigned.

**Matched episode protocol:** Not instantiated. **Participant results:** Not attempted. An AI attempt is not required for benchmark construction; actual bound materials and matched episode settings remain separate requirements.

### Current continuous measurement policy

**Disposition:** continuous\_measurement.

- [Shared reproduction and improvement policy](implementations/continuous-outcomes-v1/policy.json)
- [Authenticated continuous revision](continuous-outcomes-binding.v1.json)
- [Reviewed task amendment](implementations/continuous-outcomes-v1/TASK_AMENDMENT.json)
- [Continuous operator entrypoint](implementations/continuous-outcomes-v1/benchmark.py): `prepare`, `inspect`, `freeze`, `score`.

The source route produces continuous fixed-panel measurements. Materials admission, runtime enforcement, participant authorship and scientific claims remain separately evidenced.

### Retained pre-continuous policies

These policies and the archived task preserve their prior scope; they do not impose binary thresholds on current continuous measurements.

- [Pre-continuous task](docs/pre-continuous-outcomes-v1/task.json)
- [Retained reproduction policy](reproduction.v1.json)
- [Retained temporal improvement policy](improvement.temporal-scope.v1.json)
- [Retained outcome binding](outcomes.v1.json)
- [Retained temporal revision](primary-successor.v1.json)

### Retained author-source reproduction routes

causal-proposal, noncausal-proposal. Author calibration is not a qualified submitted AI reproduction; source-matched receipts cannot be relabeled as offline candidate receipts.

| Author source | Selector |
| --- | --- |
| Delivery | [delivery.py](implementations/source-matched-nlb-v1/delivery.py) |
| Scorer | [scorer.py](implementations/source-matched-nlb-v1/scorer.py) |
| Protocol | [protocol.json](implementations/source-matched-nlb-v1/protocol.json) |

- [Preserved definition before dual outcomes](historical/task.pre-outcomes.v1.json)

| Outcome | Information condition | Assessment | Episode protocol | Participant result |
| --- | --- | --- | --- | --- |
| Reproduction | Paper data | Continuous measurement | Not instantiated | Not attempted |
| Reproduction | Paper data author code | Continuous measurement | Not instantiated | Not attempted |
| Improvement | Paper data | Continuous measurement | Not instantiated | Not attempted |
| Improvement | Paper data author code | Continuous measurement | Not instantiated | Not attempted |

Author-baseline replay and historical reconstruction attempts retain their original scopes. They are not promoted to qualified AI reproductions or improvements by these contracts.

## Retained original registration policy

This original contract preserves its registration scope. The shared continuous policy above governs both current outcomes; this retained audit does not set current measurement thresholds.

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
- Specification identity: 15092 bytes; SHA-256 `b3306fc5757863b295fd70d3915daee9e5535e7aa6dd92ce2173d25aed91f6e3`.
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
- [Continuous outcomes v1](implementations/continuous-outcomes-v1) — Reviewed continuous outcome source.
  Scope: Bounded paired-material preparation, outcome-specific CPU profiles and complete continuous reproduction/improvement measurement preserve the exact prior task and original evaluator. The proposed current task is not activated by artifact registration; exact context/CLI/binder adoption and separately admitted authentic export remain required. AI results are separate from construction readiness, and no binary reproduction or superiority claim is inferred.
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
