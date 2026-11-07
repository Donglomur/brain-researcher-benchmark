# Neuroscience benchmark delivery workspace

Target: **100 paper projects and 100 neural-data assignments**. This workspace connects the existing source audit to executable task packages. A JSON specification is not a finished benchmark. The runner reports source specifications, verified local scoring adapters, historical native development packages and full research qualification separately.

For a current candidate/operator handoff, start with [four bounded local tasks](../docs/neuroscience-benchmarks/BOUNDED_LOCAL_TASKS.md): NLB co-smoothing, Purkinje morphology, cardiac/aperiodic reconstruction and processed dopamine-response prediction. It links the verified program routes, public allowlists and remaining original scientific commitments. In particular, use the new [Purkinje handoff](neuroscience/paper-find-rep-013-purkinje-morphology/LOCAL_RELEASE_STATUS.md) and [cardiac route guide](neuroscience/paper-root-add-016/LOCAL_RELEASE_STATUS.md) beside their preserved, source-frozen legacy READMEs. This guide makes no new task or readiness promotion.

```bash
python3 tools/neurobench.py status
python3 tools/neurobench.py list --track neural
python3 tools/neurobench.py show NEURAL-017
python3 tools/neurobench.py check
python3 tools/neurobench.py score NEURAL-017 --submission /absolute/submission.npz --output /absolute/new-result-directory
```

Add `--dry-run` to `score` to inspect the argument vector without executing it. Scorers that declare them also require `--review /absolute/review.json --other-reserve-bytes INTEGER`; the scorer validates current allocation and reservations. Legacy scorers reject these options when undeclared. Commands never launch an LLM, install dependencies, download datasets or send a candidate packet to a model service. Scoring uses the local Docker environment and data assets identified by each package. Run from a host with access to the configured Docker daemon. Candidate submissions are data files; these scoring adapters do not execute candidate programs.

## Current structure

- `manifests/paper/<canonical-id>.json`: 100 task-specific paper build specifications, including central outputs, pinned source routes, code revisions, available asset identities and unresolved evaluation requirements.
- `manifests/neural/<canonical-id>.json`: 100 neural build specifications, including measurements, permitted context, biological grouping, target, metric, source audits and controls.
- `neuroscience/<package>/manifest.json`: an implemented package's exact score command, public/private asset references, source identity, declared scope and measured verification receipt.

Generated specifications always retain `status=specification_only`, null executor/scorer references and false admission flags. Executable adapters are registered independently. The runner rejects unknown IDs, altered verification receipts and changed scoring entrypoints. It refuses missing adapters and existing output paths; it does not return a dummy success score for an unfinished task.

## What the current adapters establish

| Canonical assignment | Executable scope | Evaluation meaning |
|---|---|---|
| NEURAL-005 | Next-round rejection prediction using current/past behavioral and ERP features, with seven development participants | Continuous participant-mean log loss, Brier/AUC/calibration and signed differences from three fixed references; static file scoring does not certify prefix access |
| NEURAL-007 | Whole-night prediction from engineered EEG/EOG/clock features and shared pretrained-model outputs; six training and two exposed development people | Continuous participant-mean macro-F1 and signed comparator differences; no invented pass floor |
| NEURAL-008 | Paired EEG versus EEG+EOG development-night predictions from two exposed people | Separate absolute macro-F1/REM metrics and signed modality differences; weak EEG cannot earn credit merely by inflating the difference. File scoring does not establish matched program provenance. |
| NEURAL-017 | MC_Maze motor-population co-smoothing on the qualified training/validation panel | Continuous held-out Poisson bits/spike and signed difference from the condition/time comparator |
| NEURAL-018 | MC_Maze forecasting from earlier activity and condition metadata, using a 200 ms future window | Continuous future bits/spike and signed differences from five references; pooled condition (0.15065) exceeds ridge (0.11074), with original negative results retained |
| NEURAL-019 | Retrospective hand-velocity decoding across eight held maze groups, with four fixed representation/readout references | Continuous equal-group R² and signed comparisons; raw137 0.37434, PCA10 0.14179, random10 −0.19086 and phase only −0.28151; one shared macaque session |
| NEURAL-023 | Across-day velocity decoding from one Indy macaque over two dates; arbitrary submitted-file scoring | Continuous mean-axis R² and error metrics against seven fixed references; balanced pool 0.38277 versus calibration-only 0.32739. File scoring alone does not attest provenance; the separately qualified program path commits output before grading. |
| NEURAL-034 | Context prediction from fixed glial calcium windows with seven held-mouse folds | Separate mouse-macro balanced accuracy and log loss; glial 0.72857/0.85211 versus behavioral proxy 0.64286/0.66735, retaining the accuracy/calibration tradeoff |
| NEURAL-077 | ERP CORE target-versus-nontarget prediction from eight people, with six training and two exposed development participants | Balanced accuracy and log loss against EEG, ocular, gross-amplitude and history controls; gain in classification does not imply improved calibration |
| NEURAL-095 | Produced-interval prediction from a fixed pre-Set DMFC spike window in one macaque session | Continuous MAE/RMSE and all five fixed reference comparisons; total-spike MAE 77.01 ms versus condition median 78.96 ms |
| NEURAL-058 | Existing single-session wheel-speed development task | Prescribed-recipe numerical control; not the complete broader roster investigation |
| PAPER-ROOT-ADD-003 | Existing bounded language-network reconstruction | Declared historical numerical reconstruction control; complete paper/access/improvement study remains open |
| PAPER-FIND-003 | Three specified human hippocampal-ripple learning mixed-model artifacts | Separate coefficient, full covariance, variance, support and contrast errors; partial coverage stays explicit. No candidate-program execution or whole-paper claim. |
| PAPER-FIND-NEW-001 | Source-recipe astrocyte sequence reconstruction across21records from14mice | All21 artifact checks, retaining18finite and3insufficient outcomes; prescribed numerical recipe, not open-paper assessment |
| PAPER-FIND-NEW-002 | Released sequence-filtering Figure 2 B/C slopes and one 59-cell example | Continuous response/slope error with separate evidence checks; central six-experiment biology remains open. |
| PAPER-FIND-REP-013 | Existing ten-tree Purkinje morphology reconstruction | Declared raw-tree calculation and discrepancy control; whole-paper claims remain unresolved |
| PAPER-ROOT-ADD-016 | Six posterior-summary targets for the original 655-person Salzburg processed CSV | Continuous posterior-SD-scaled discrepancies, valid stochastic alternatives and explicit Monte Carlo limits; inference provenance and the full paper remain separate |
| PAPER-ROOT-ADD-020 | Archived 50-ms IT face-memory response geometry across AM/PR/TP neurons | Continuous equal-curve reconstruction error with mean/SEM/count diagnostics; manuscript 100-ms and population-inference scope remains open |
| PAPER-paper-signal-add-020 | Three specified conditional ERP mixed-model summaries over 6,403 trials and 41 participants | Continuous coefficient error; covariance, row-accounting and contrast-report checks remain separate. Zero coefficient error alone is not scientific success. |
| PAPER-paper-signal-add-021 | V1 working-memory behavioral reconstruction from 14,061 trials and 15 participants | Continuous cell-mean error plus separate contrast/uncertainty consistency; source and paper discrepancies remain explicit. The qualified program path also verifies input-dependent computation. |
| PAPER-paper-method-001 | One-session dimensionality reconstruction with one full and 18 fixed nonfull panels | Continuous numerical errors for corrected/naive moments and ratios; 76 nested records are one task |
| PAPER-FIND-ADD-015 | Processed-trace optogenetic attenuation reconstruction for central Figure 2/3 responses and a Figure 4 subset | Continuous numerical reconstruction error; two published p-value discrepancies and animal-identity limitations remain explicit |

Each package has accepted its saved valid reference and rejected the declared invalid controls in a real isolated scoring run. The predictive scorers preserve lower and negative comparisons. Those checks establish usable local scoring under the documented scope, not blind agent performance, independent population generalization, hosted compatibility or full scientific admission. Public/private paths in operator manifests are not themselves an agent sandbox; release only each package's stated public allowlist to a candidate.

All current data are development material. Shared studies, animals, stimuli, code-access conditions, model seeds and nested outputs do not create additional independent benchmark IDs. The original 200-ID rosters remain unchanged. The three pre-existing native packages also appear in the new scoring interface; they are counted once.

## Rebuilding source specifications

```bash
python3 tools/build_paper_delivery_manifests.py
python3 tools/build_neural_delivery_manifests.py
python3 tools/build_paper_delivery_manifests.py --check
python3 tools/build_neural_delivery_manifests.py --check
```

These are metadata operations. They do not acquire data, qualify scientific results or turn the other assignments into working tasks. Follow the task-specific next implementation action and retain new acquisition, reference, control and replay receipts before updating runtime status. See the [live construction record](../docs/neuroscience-benchmarks/BUILD_STATUS.md) for actual progress and current constraints.

## Submitted-program execution

Runners that declare per-run review inputs also require `--review /absolute/review.json --other-reserve-bytes INTEGER`. The review must be an ordinary repository file; the pinned runner checks its exact authorization, source version, current cumulative cost and storage reservations. `--dry-run` only constructs the command and does not validate or grant execution authority. Legacy runners retain their existing arguments and reject these options when undeclared.

`python3 tools/neurobench.py run ID --program /absolute/program.py --output /absolute/fresh-run --dry-run` resolves a separately qualified program wrapper when one is registered. Scoring qualification alone never enables it. Metadata validation checks the wrapper, source closure and terminal control evidence. NEURAL-095 now has a separately qualified program runner. A program computed its predictions from public training data; malformed output and private-path probes rejected before any private target read. An actual interrupted-wrapper check passed after a narrow Python-startup identity repair. The failed first qualification remains recorded. See [runner evidence](../authoring/dmfc-timing/program-runner-v2/RESULTS.md) and the [local run guide](neuroscience/neural-095/RUN_PROGRAM.md). Future attempts also require an explicit recorded operator compute allowance; the construction qualification budget is not reset or reused.

NEURAL-034 also has a separately qualified [seven-fold program runner](../authoring/shared-program-runner-v2/RESULTS.md). One program is committed before any fold; each held-mouse fold runs in fresh state and commits predictions before the next fold is released. The final private grade reproduces the fixed reference metrics. Its seven folds remain one benchmark ID.

NEURAL-077 now has a separately qualified [feature-only EEG program runner](../authoring/erp-core-target-v1/program-runner-v1/RESULTS.md). It provides six labeled training people and two unlabeled development people in one batch, with all candidate resources removed before isolated validation/scoring. Raw signals remain outside this observation condition.

The NEURAL-095 runner also passed a [clean-copy setup rehearsal](../authoring/dmfc-timing/clean-copy-v1/RESULTS.md):59pinned files, candidate and grader mounts confined to that copy, the expected score, and complete cleanup. This qualification uses already acquired assets and the same host/image.

NEURAL-017 also has a qualified [co-smoothing program runner](../authoring/nlb-cosmoothing/program-runner-v1/RESULTS.md). The public training/query packet supports one committed program; all candidate resources are removed before the unchanged private scorer runs. Its fresh ridge control reproduced the existing development result, with malformed-output and private-path controls passing. Its [clean-workspace setup check](../authoring/nlb-cosmoothing/clean-copy-v1/execution-001/receipt.json) now passes with exact prediction parity, verified public/private mounts and complete cleanup; this is the same host and image, not an independent-machine installation.

NEURAL-018 also has a qualified [forecasting program runner](../authoring/nlb-forecast-v1/program-runner-v1/RESULTS.md). It exposes earlier counts, condition context and training-only future labels, then scores a committed future-rate archive after candidate cleanup. Its capacity control validates the full34MiB output contract, and all five fixed comparator differences remain visible.

NEURAL-019 has a qualified [movement-decoding program runner](../authoring/nlb-movement-v1/program-runner-v1/RESULTS.md). It supplies training trials and unlabeled held-maze queries, commits predictions, then removes candidate resources before private scoring. Its positive control reruns all 51 original ridge solves; four signed reference comparisons and the exposed single-session scope remain explicit.

PAPER-paper-signal-add-020 has a qualified [paired ERP paper program runner with corrected candidate materials](../authoring/reward-emotion-erp/program-runner-v2/RESULTS.md). The common CLI selects paper+data (A); the documented direct wrapper also selects paper+data+code (B). Both views execute programs and score continuous coefficient, covariance and reporting components. The same positive reference program passed both corrected views. A has 18 files and B has 22, adding only four official source files; no LLM comparison or improvement is claimed.

NEURAL-007 has a qualified [whole-night feature program runner](../authoring/sleep-eog/program-runner-v1/RESULTS.md). One program receives identical six-person training inputs in fresh state for each development night. Both predictions are committed before scoring. Use the explicit review and reservation arguments described in the [operator runbook](../authoring/sleep-eog/program-runner-v1/OPERATOR_RUNBOOK.md); its template grants no execution authority. Raw-signal and investigator modes remain unqualified.

NEURAL-023 now has a qualified [across-day program runner](../authoring/rtt-transfer-v1/program-runner-v1-preparation/RESULTS.md). It gives one committed program the four fixed public packet files, captures bounded predictions, removes producer resources, then invokes the unchanged private scorer. The fresh 51-fit positive control reproduced the reference; valid negative, malformed/lingering and named-private-path controls passed. All 15 resources and two process groups were absent. Its batch access is retrospective, and this is a known-control qualification rather than a new LLM or native-understanding result.

PAPER-paper-signal-add-021 has a qualified [behavioral CSV program runner](../authoring/v1-tms-memory-v1/program-cli-v1/RESULTS.md). A single positive program reconstructs original, fixed-transformed and hand-derived inputs; stale and coherent null outputs receive poor continuous scores, and missing output rejects. The ordinary direct positive and common-CLI null runs reproduced their earlier complete scores. Historical p-value/effect-size provenance and whole-paper reconstruction remain unresolved.
