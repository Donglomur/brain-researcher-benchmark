# SMC-RNN: reproduce and improve with paper/data versus official code and released models

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

**Primary access pair:** `paper_data` versus `paper_data_author_code_and_weights`. Both conditions receive identical permitted observations, paper, task and per-outcome resource settings. Only the assisted condition receives the exact official code and ten pinned released-model assets. Faithful released-model inference is allowed reproduction in that condition; it does not establish independent training. Actual asset use and participant execution remain separately evidenced.

### Current continuous measurement policy

**Disposition:** continuous\_measurement.

- [Shared reproduction and improvement policy](implementations/continuous-outcomes-v2/policy.json)
- [Authenticated continuous revision](continuous-outcomes-binding.v2.json)
- [Reviewed task amendment](implementations/continuous-outcomes-v2/TASK_AMENDMENT.json)
- [Continuous operator entrypoint](implementations/continuous-outcomes-v2/benchmark.py): `prepare`, `inspect`, `freeze`, `score`.

Released-model inference is allowed in the assisted condition. Actual asset use, execution fidelity, independent training and scientific claims require separate evidence; no checkpoint is loaded by this operator interface.

- [Exact official-asset allowlist](implementations/continuous-outcomes-v2/asset_allowlist.json)

### Retained source-only continuous policy

The historical `paper_data_author_code` condition remains a separate source-only ablation. It is not pooled with the current code-and-weights pair.

- [Preserved source-only task](docs/pre-official-assets-v2/task.json)
- [Retained source-only policy](implementations/continuous-outcomes-v1/policy.json)
- [Retained source-only entrypoint](implementations/continuous-outcomes-v1/benchmark.py)
- [Retained source-only revision](continuous-outcomes-binding.v1.json)

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
| Reproduction | Paper data author code and weights | Continuous measurement | Not instantiated | Not attempted |
| Improvement | Paper data | Continuous measurement | Not instantiated | Not attempted |
| Improvement | Paper data author code and weights | Continuous measurement | Not instantiated | Not attempted |

Author-baseline replay and historical reconstruction attempts retain their original scopes. They are not promoted to qualified AI reproductions or improvements by these contracts.

## Retained original registration policy

This original contract preserves its registration scope. The shared continuous policy above governs both current outcomes; this retained audit does not set current measurement thresholds.

**Disposition:** design\_ready. The complete original endpoint, author code/checkpoints and original scorer are recovered. Source preparation and qualification have executable routes; no full author score match, candidate superiority or final admission policy is established.

- [Retained original improvement contract](improvement.v1.json)
- [Initial source-paper task registration (no predecessor)](../../../docs/provenance/registrations/paper-initial/PAPER-SMC-RNN-2024.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Recorded public evidence

Each record keeps the scope of its original report. It is not current runtime qualification.

- [Author model inference probe — causal author model, 192 particles, filtered outputs](docs/native-cost-characterization.json): Actual selected author-checkpoint inference on the first train and eval chunks only; no complete predictions, scores or 32-repeat baseline.
- [Author model inference probe — noncausal author model, 192 particles, filtered outputs](docs/native-cost-characterization.json): Actual selected author-checkpoint inference on the first train and eval chunks only; no complete predictions, scores or 32-repeat baseline.
- [Author reference calibration — causal released author model, 192 particles and 32 averaged repeats](../../../docs/science/smc-author-calibration-20261117.json): Complete selected author predictions and four original aggregate metrics; recovered noncausal output retains its failed supervisor.
- [Author reference calibration — noncausal released author model, 192 particles and 32 averaged repeats](../../../docs/science/smc-author-calibration-20261117.json): Complete selected author predictions and four original aggregate metrics; recovered noncausal output retains its failed supervisor.
- [Historical reference rescore — causal frozen historical/current-release author prediction, original MC\_Maze 20 ms scoring](../../../docs/science/smc-historical-rescore-20261120.json): Successful bounded rescoring of a complete previously frozen author prediction; no new author-model inference or AI candidate.
- [Historical reference rescore — noncausal frozen historical/current-release author prediction, original MC\_Maze 20 ms scoring](../../../docs/science/smc-historical-rescore-20261120.json): Successful bounded rescoring of a complete previously frozen author prediction; no new author-model inference or AI candidate.
- [Participant material preparation](docs/official-assets-materials-v2-20261117.json): Complete external 71-file paper/data and author-code/released-model material pair; payloads are not published in this report.
- [Paper source preparation](docs/source-preparation-evidence.json): Complete original MC\_Maze 20ms input preparation and paired participant materials, with generated source/scorer controls. This report excludes separately recorded author-model timing and all scientific performance evaluation.

Inspect conditions, metrics and limits with `python3 scripts/neurobench.py evidence PAPER-SMC-RNN-2024`. Programme evidence does not establish direct interpretation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 16782 bytes; SHA-256 `e99cf60035a156fdb7a0a3b61b539db387ae53b31f1d4be59da31f18d9346fbd`.
- [Registration and provenance](../../../docs/provenance/registrations/paper-initial/PAPER-SMC-RNN-2024.json)

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Original two-arm scientific comparison and scope](docs/scientific-contract.json)
- [Source preparation and paired-export engineering evidence](docs/source-preparation-evidence.json)
- [Partial native execution and full-run cost estimates](docs/native-cost-characterization.json)
- [Official-assets v2 material preparation and inspection receipt](docs/official-assets-materials-v2-20261117.json)
- [Cached-image dependency metadata inventory; scientific runtime unqualified](docs/scientific-image-inventory-20261117.json)
- [Current adopted v2 source and completed material preparation; runtime and scientific outcomes remain unqualified](docs/current-source-status-20261118.json)

## Implementation artifacts

- [Aggregate episode v1](implementations/aggregate-episode-v1) — Reviewed source component.
  Scope: Aggregate episode source now selects the accepted5658-byte paired-material manifest a88725a6d3b8c7509826d7c9a4034c796a04635e4bce80cb887468e688f976bc. Existing scientific endpoint, schemas, scorer and access-condition budgets are preserved. Deployment binding remains unresolved; source selection does not qualify image/cgroup/PID limits or launch, and does not establish reproduction, improvement or SOTA.
- [Aggregate owner v1](implementations/aggregate-owner-v1) — Reviewed source component.
  Scope: Trusted aggregate-owner source and its existing process/cgroup/transport dependencies align to the selected material binding. The source status sentence and dependency/legacy pins change, without execution-policy or numerical changes. Genuine deployment, private material admission and benchmark execution remain unresolved; no model or scientific result is inferred.
- [Author reference v1](implementations/author-reference-v1) — Reviewed source component.
  Scope: Create-only protected author-reference adapter for serial B/B author\_reference phases, using the existing full-panel facade and helper closure without copying dependencies. Preserves participant A/B source, the original 192x32 panel, seeds and four metrics, bounded stable snapshots before target reads, failure closure and owner qualification gates. The public entry uses a fresh external artifact leaf disjoint from the repository. Generated source controls and the entry-only check do not establish authentic model execution, participant qualification, AI reproduction, improvement or scientific readiness.
- [Full panel improvement v1](implementations/full-panel-improvement-v1) — Full panel offline transductive improvement source.
  Scope: Separately versioned full-panel offline improvement source for the original MC\_Maze 20-ms task. Its source controls cover new material identities, TRAIN/VALID development views, frozen methods and declared adaptation, two access-condition owner phases, and the original four-metric scoring boundary. Thirty-two earlier public controls and one additional private source-closure control passed. Six paired pretest-preparation controls also passed, including a separate portability check; these establish no scientific result. A fresh full-panel pair has been constructed and authenticated: 71 files / 31,380,768 bytes under the new condition identities. Both pretest development views were constructed and accepted: 68 view files / 30,383,017 bytes plus a 2,204-byte paired handoff (69 files / 30,385,221 bytes total), with supplied TEST input excluded and admitted TRAIN/VALID data retained. Actual authoring process custody/resources and actual Linux runtime qualification remain outstanding. The existing strict/reproduction conditions and their material identities remain unchanged. Portable prepare/inspect/execute/protected-grade entry with retained generated20-control proof; fixed2GiB,600/605CPU-s,720work+60cleanup seconds. Actual physical runtime/ABI/whole-grader qualification remains outstanding.
- [Gain calibration v1](implementations/gain-calibration-v1) — Reviewed source component.
  Scope: Reviewed source-only nine-gain calibration for the same frozen restricted VALID reference, with four generated controls. No real gain selection, original inference or scoring. Released configuration declares val; actual run/configuration, local weight/release, Table 2 and DANDI lineage remain unproved. VALID checkpoint selection is development exposure. Authentic TEST binding and candidate-aware TEST grading remain future.
- [Historical reference grade v1](implementations/historical-reference-grade-v1) — Reviewed source component.
  Scope: Reviewed historical-reference grading source for the existing SMC task, with fixed runtime helpers, scorer and reference panel. Source-only qualification; no new score or inference, exact paper reproduction, improvement, SOTA or physical containment claim.
- [Offline nlb outcomes v1](implementations/offline-nlb-outcomes-v1) — Offline whole trial outcome policy delivery and scoring source.
  Scope: Reviewed source for the offline whole-trial NLB outcome successor, including policy, delivery, scoring and generated controls. It reuses retained source-matched scorer, delivery and protocol dependencies. Registration does not activate a runtime or qualify reproduction or improvement; trusted episode policy, authentic execution, receipt provenance and numerical scientific outcomes remain separately required and unestablished. Existing task definitions, histories and retained source artifacts are preserved.
- [Participant preflight v1](implementations/participant-preflight-v1) — Reviewed source component.
  Scope: Participant-only complete prediction formatting preflight against the unchanged SMC validator and public panel metadata. Fifteen generated controls passed. No paired operator materials, other-condition inputs or targets are required; semantic ordering, actual participant execution and scientific qualification remain unestablished.
- [Restricted validation owned episode v1](implementations/restricted-validation-owned-episode-v1) — Reviewed source component.
  Scope: Reviewed restricted VALID ownership source and four generated controls: pre-request read-only exposure, attachment acknowledgement before release, and closure-gated frozen-output custody. No original inference, numerical grading, runtime or physical containment qualification. Checkpoint-fit cohort remains unresolved; VALID is development data and the original TEST route is unchanged.
- [Restricted validation v1](implementations/restricted-validation-v1) — Reviewed source component.
  Scope: Reviewed restricted VALID source, callable interfaces and generated controls; no original-array projection, model inference, numerical grading, calibration, improvement or scientific qualification. VALID is development data; historical checkpoint cohort and paper links remain unresolved.
- [Source matched nlb v1](implementations/source-matched-nlb-v1) — Original panel preparation, paired materials and frozen prediction scoring.
  Scope: Original MC\_Maze 20-ms input preparation, historical source-only delivery, author reference and scoring routes. Both complete selected author predictions and aggregate metrics are recorded separately in docs/science/smc-author-calibration-20261117.md; the noncausal aggregate is accepted recovered reference output with its failed supervisor preserved. The separately reviewed version2 assisted material pair contains 71 files and ten released assets. These records do not qualify participant execution, exact paper linkage, AI reproduction, improvement or SOTA. Original test targets are publicly exposed.
- [Test candidate grading v1](implementations/test-candidate-grading-v1) — Reviewed source component.
  Scope: Reviewed source and generated controls for candidate-aware TEST grading after a completed restricted VALID gain selection. Retains all four TEST metric vectors and candidate-minus-reference deltas; selection on VALID co-bps does not establish improvement on every metric. The fixed grid changes global rate calibration only. Public TEST exposure and uncertain checkpoint-run, Table 2 and DANDI lineage remain explicit. Original-data execution, authentic candidate selection, runtime/material admission and scientific qualification remain future.
- [Continuous outcomes v1](implementations/continuous-outcomes-v1) — Reviewed continuous outcome source.
  Scope: Historical source-only continuous policy and preserved preparation/measurement source. The current primary is the separately adopted official-assets v2 task, whose original 71-file material pair is recorded in docs/official-assets-materials-v2-20261117.json. Version1 source, policy and packet identities remain unchanged and cannot be relabeled as v2. Protected participant execution, AI reproduction/improvement and scientific qualification remain separately unestablished; no binary reproduction, meaningful superiority or SOTA claim is inferred.
- [Continuous outcomes v2](implementations/continuous-outcomes-v2) — Reviewed continuous outcome source.
  Scope: Current adopted official-assets v2 source for paper\_data versus paper\_data\_author\_code\_and\_weights, with the exact ten-asset allowlist, typed use declarations and unchanged original evaluators. The existing exact-task-bound material report records the original 71-file, 31,393,479-byte pair as independently verified. docs/current-source-status-20261118.json contextualizes only the frozen proposal-phase adoption/export clauses; task, policy, material and verifier identities remain unchanged. Protected participant/runtime qualification, model execution and AI reproduction/improvement remain unestablished. Released-asset assistance is not independent training; no equivalence, meaningful superiority, binary success or SOTA claim is inferred.
- [Long owner v1](implementations/long-owner-v1) — Reviewed source component.
  Scope: Parent-held process ownership and public grade-dispatch source preserve the original SMC arm ceilings and producer resource profiles. The accepted Linux CI selection is twelve explicitly named metadata/mock methods and twenty-nine bridge methods; six actual-process methods retain only their observed macOS proof and remain Linux-unqualified. Linux pidfd/subreaper, immutable image, Docker normal/forced-stop lifecycle, host-loss recovery, generic subprocess/thread compatibility and authentic candidate/model execution remain separately unqualified.
- [Paired reproduction v1](implementations/paired-reproduction-v1) — Joint original source method reproduction evaluation.
  Scope: Joint freeze and scoring interface for two complete original-method prediction sets and all eight source findings through the unchanged evaluator. This source component does not supply an agreement policy, establish original-method execution or qualify AI reproduction, historical source linkage, candidate isolation or scientific performance.
- [Protected episode v1](implementations/protected-episode-v1) — Reviewed source component.
  Scope: Protected episode source retains the selected continuous SMC reproduction/improvement conditions, original budgets and grading boundaries. Generated scientific-lane controls do not establish actual Linux/Docker lifecycle, protected candidate execution or scientific performance. The separately reviewed long-owner source is additive and does not rewrite this predecessor refusal or policy.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/mackelab/smc_rnns)
- [Paper](https://papers.neurips.cc/paper_files/paper/2024/file/209423f076b6479ab3a4f45886e30306-Paper-Conference.pdf)
- [Source](https://doi.org/10.48324/dandi.000128/0.220113.0400)
- [Source](https://github.com/mackelab/smc_rnns)
- [Source](https://papers.neurips.cc/paper_files/paper/2024/file/209423f076b6479ab3a4f45886e30306-Paper-Conference.pdf)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
