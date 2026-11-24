# Current status and recorded evidence

The repository contains usable source and scoped execution evidence. Complete
scientific qualification requires additional evidence for each task's declared
population, access condition, comparator and evaluation boundary. Registration,
source availability, software verification and model performance are reported
separately.

The current goal has [four first-class outcomes](../design/four-outcomes.md): paper
reproduction, paper improvement, native neural interpretation and neural tool/model
building. The evidence below keeps these outcomes separate. This design change
does not itself qualify a reproduction, an improvement or either neural outcome.

The latest [fixed-image EEG pilot](../../benchmarks/neural/NEURAL-077/docs/exploratory32-fixed-image-pilot-20261122.md)
reports direct-image and generated-programme results on the same 32 queries.
The [REVE CPU profile](../../benchmarks/paper/PAPER-paper-method-003/implementations/matched-reference-v1/CPU_PROFILE.md)
records a training compatibility check that passed numerically but exceeded its
memory ceiling. Neither establishes a paper reproduction or improvement, SOTA,
or complete benchmark qualification.

The earlier [November 18 public progress update](public-progress-2026-11-18.md)
links the 936-case ABR observation release, the Jaxley original-data diagnostic
and the NEURAL-063 original metadata qualification. These earlier reports retain
their original scopes.

From the repository root:

```sh
python3 -I -S -B scripts/neurobench.py status
python3 -I -S -B scripts/neurobench.py evidence
python3 -I -S -B scripts/neurobench.py evidence NEURAL-077
python3 -I -S -B scripts/neurobench.py evidence PAPER-paper-method-003
python3 -I -S -B scripts/neurobench.py evidence PAPER-paper-method-013
python3 -I -S -B scripts/neurobench.py evidence PAPER-SMC-RNN-2024
python3 -I -S -B scripts/neurobench.py evidence NEURAL-096
python3 -I -S -B scripts/neurobench.py neural-contract NEURAL-077
python3 -I -S -B scripts/neurobench.py implementations NEURAL-007
python3 -I -S -B scripts/neurobench.py operator routes
```

`status` derives inventory and contract counts from the current registry and counts
records within an explicit set of public reports. `evidence TASK_ID` returns the
reported condition, scope, metrics, comparators, limitations and source hashes.
Neither command opens private inputs or reruns an experiment. The CLI exposes
its explicitly indexed reports; historical counts retain the scope of their
original report rather than incorporating later experiments automatically.

The [common operator route](../operator-routes.md) verifies current source for
NEURAL-077's 400 EEG trials and NEURAL-007's 5,450 sleep epochs. With the exact
external assets provisioned, its `inspect` command authenticates the public inputs;
`prepare`, `validate` and `grade` connect to the task's existing implementations.
Discovery through `operator routes` reports source availability only. These routes
use two previously exposed development people per task; software controls or
finished-submission scores do not become new solver attempts or unseen-population
evidence.

## What has been observed

| Evidence | Recorded scope | What it establishes |
| --- | --- | --- |
| [Difficulty pilot](../science/difficulty-pilot-20261117.md) | Eight scored attempts on four task IDs: four historical paper-calibration attempts and four neural prediction-programme attempts | Outcomes for the exact reported development endpoints and conditions, with baseline comparisons; no whole-task qualification or paper improvement |
| [NEURAL-077 fixed-image pilot, November 22](../../benchmarks/neural/NEURAL-077/docs/exploratory32-fixed-image-pilot-20261122.md) | 32 fresh direct-image episodes and one frozen generated programme on the same 32 queries from 32 people, with four demonstrations | Direct balanced accuracy 57.1%, programme 26.8%; all failures counted incorrect. Exploratory participant results, with instruction-only tool restrictions, unmatched compute and no full-task qualification |
| [NEURAL-077 full32 image-reference failures, November 24](../../benchmarks/neural/NEURAL-077/docs/full32-image-reference-calibration-20261124.md) | Two failed engineering executions, one preflight-only; one reference fit and 62 query capture attempts with 61 complete captures, out of 6,400 selected queries | No scoring, AI attempt or successful calibration. A label-free diagnostic found fixed-view clipping removed post-marker support; both failures and all unattempted cases remain |
| [NEURAL-077 waveform preparation](../../benchmarks/neural/NEURAL-077/implementations/complete-direct-condition-v1/EVIDENCE.json) | All 400 query waveforms and four demonstrations compared with pinned raw samples | Authentic-input materialization; no model execution or scoring |
| [NEURAL-077 full32 numerical materialization](../../benchmarks/neural/NEURAL-077/docs/full32-materialization-20261119.md) | 32 people, 6,400 queries and the same four demonstrations; 72 saved files independently authenticated | Accepted numerical material and metadata; no AI/model evaluation, provider-isolation qualification or full visual-condition result |
| [NEURAL-077 viewer rendering](../../benchmarks/neural/NEURAL-077/implementations/visual-viewer-v1/EVIDENCE.json) | Full packet authentication and rendering of selected query ordinals | Authentic image-generation behavior; no evaluated viewer-model episode |
| [NEURAL-077 restricted viewer transport](../../benchmarks/neural/NEURAL-077/implementations/visual-transport-v1/EVIDENCE.json) | All 400 authentic queries delivered to fresh scripted clients, complete unscored response collection and 15 authentic boundary checks | Local image/action transport and collection behavior; no model/provider delivery qualification or neural interpretation result |
| [Native EEG/sleep operator controls](operator-controls-20261116.json) and [fresh-checkout repair validation](operator-controls-rename-20261116.json) | 16 fixed-output controls across two reports, covering the complete 400-trial EEG and 5,450-epoch sleep development panels | Input preparation, validation, grading, incomplete-submission rejection and target-pin failure, including the repaired public entry point; no new solver attempts, model calls or fits |
| [REVE source preparation](reve-source-preparation-20261116.json) | All 654 official EDFs, 109 participants and 9,837 prepared epochs; fixed-output software controls on the complete original test-event panel | Released-code input preparation and scorer behavior; no author-model inference, with historical preprocessing, downstream classifier and run-aggregation identity unresolved |
| [REVE CPU compatibility, November 23](../../benchmarks/paper/PAPER-paper-method-003/implementations/matched-reference-v1/CPU_PROFILE.md) | Batch 32 plus tail 28, two linear-probe steps and one fine-tuning step; 60 distinct training examples and 92 presentations | Numerical updates and checkpoint/logit reload checks passed; 8.51 GiB peak child RSS exceeded the frozen 8 GiB ceiling, so overall qualification failed. No complete fit, held predictions or score |
| [DeepCaImX source preparation](deepcaimx-source-preparation-20261116.json) | All ten original manual ROI files, 1,563 ROIs and eight donors; target-backed arithmetic controls | Reference conversion and segmentation scorer behavior; no movie-to-mask model, with crop/frame mapping, checkpoint equivalence and native assembly unresolved |
| [SMC-RNN source preparation](../../benchmarks/paper/PAPER-SMC-RNN-2024/docs/source-preparation-evidence.json) | Complete original MC_Maze 20-ms inputs and paired participant materials; 2,869 trials and 182 neurons | Authentic source preparation and matched material export; no participant episode or author-baseline qualification |
| [SMC-RNN native inference probes](../../benchmarks/paper/PAPER-SMC-RNN-2024/docs/native-cost-characterization.json) | Two selected author models exercised on first train/evaluation chunks with the original 192 particles | Native inference cost characterization, separately from generated memory controls; no complete predictions, score, full 32-repeat calibration or candidate attempt |
| [SMC-RNN author calibration](../science/smc-author-calibration-20261117.md) | Both complete selected author predictions at 192 particles × 32 repeats and four original metrics per arm | Accepted reference outputs; noncausal supervisor remains failed. No candidate/AI study, paper-reproduction threshold, uncertainty estimate or SOTA claim |
| [SMC-RNN frozen-reference rescoring, November 20](../science/smc-historical-rescore-20261120.md) | One shared bounded operation scored both complete existing predictions, with all four original metrics per model | Successful recorded evaluator and owned-process closure; six values match the earlier calibration exactly and velocity R² differs by ±1.11×10⁻¹⁶. No new author-model inference or AI attempt; the earlier failed supervisor remains failed |
| [SMC-RNN version2 materials](../../benchmarks/paper/PAPER-SMC-RNN-2024/docs/official-assets-materials-v2-20261117.json) | Independently verified external 71-file pair, 31,393,479 bytes, with ten released assets only in the assisted condition | Material preparation and access separation; no participant episode, model/scoring run or scientific outcome |
| [NEURAL-096 Set–Go preparation](../../benchmarks/neural/NEURAL-096/implementations/full-set-go-v1/AUTHENTIC_PREPARATION.json) | All 204 declared nominal-800-ms training/validation trials, 54 released units and 81,311 spikes; saved-packet consistency audit | Complete declared observation preparation, with no fitted trajectory, prior contrast, uncertainty estimate, participant episode or model trial |
| [Historical execution projections](../provenance/execution/historical-evidence-v1/README.md) | Three profiles, including four NEURAL-023 programme controls | Retained historical execution and interface-control evidence; current environments and complete scientific scope remain unqualified |

These reports overlap. Together they reference **nine distinct registered task
IDs**; source preparations, engineering controls and repeated reports do not create
additional benchmarks. The earlier eight-attempt difficulty pilot evaluated neural
programmes on exposed development people and has no direct/viewer AI predictions.
The separate November 22 pilot adds direct-image episodes within NEURAL-077;
32 applications of one frozen programme are not 32 independently authored methods.
No interactive-viewer model result is reported here.

The fixed-image pilot had four target and 28 standard events. It retained one
direct delivery error and six programme runtime errors in both arms' denominators.
The direct arm's conditional 95% balanced-accuracy interval was 30.4–76.8%, which
includes the 50% baseline; its point estimate does not establish reliable
above-baseline performance. The paired direct-minus-programme gap was 30.4
percentage points, with a conditional interval of 1.8–53.6 points. This comparison
includes delivery/runtime reliability and uses one generated programme, unmatched
compute budgets and instruction-only restrictions. Exact model snapshots and full
tool traces were unavailable. It cannot establish a general native-versus-tools
advantage, physiological P3 detection, the full 6,400-case condition or SOTA.
The report links the frozen programme and retains a subsequent diagnostic without
revising the original predictions or scores. Private per-case inputs and records
are not included, so the public artifacts alone cannot reproduce those scores.

The two historical SMC-RNN author-model probes are actual bounded inference operations,
reported separately from the eight historical solver attempts and 16 native
operator controls. They produced no complete prediction set or score and added
no new candidate or solver episode. Generated repeat-allocation controls did not
execute a model and are separate from those probes. Later, both complete author
predictions and all eight original metric aggregates were authenticated; the
noncausal aggregate was accepted as recovered reference output with its failed
supervisor preserved. The calibration report retains its original draft and
publication-pending assembly flags; neither these flags nor the accepted scalar
outputs establish an AI reproduction or improvement result.

The later [November 20 rescoring report](../science/smc-historical-rescore-20261120.md)
records a successful shared scoring operation for both frozen predictions. It took
22.07 seconds; the grader container and recorded host processes closed. The
unchanged velocity evaluator includes its original training-split decoder fitting,
but no author model was trained or rerun. Its two scored models count as one
rescoring operation and add no task or AI attempt. This accepted result preserves
both earlier failures and does not establish exact paper reproduction, improvement,
or fresh runtime qualification of every current implementation.

The native controls retained failures as well as accepted fixed-output scores.
Incomplete submissions were refused before private-stage dispatch, with zero
target-loader attempts; deliberately wrong target bytes failed the existing pin
check. Across both reports, cleanup verified that all 24 owned containers were absent. These controls
establish the reported software behavior at the captured source and environment,
not the quality or provenance of an independently authored candidate.

Current source routes for the retained historical profiles are the
[Purkinje task](../../benchmarks/paper/PAPER-FIND-REP-013/README.md),
[across-day velocity task](../../benchmarks/neural/NEURAL-023/README.md) and
[TMS task](../../benchmarks/paper/PAPER-paper-signal-add-021/README.md).
The historical report itself keeps its original source namespace.

The reports and their original limits remain available even when a task definition
or runtime changes. Source hashes identify the published report being read; they
do not independently authenticate the original executed environment.

## Current scientific definitions

Paper reproduction and paper improvement are distinct first-class outcomes.
Reproduction assesses faithful recovery of the complete declared original result
under specified source, data and evaluation conditions. Improvement assesses
superiority on that same task, with its fixed observations, cohort, split, metric,
aggregation and required controls. Improvement candidates may change architecture,
inference or optimization within the permitted observation and budget boundary.
The source-author recipe constrains reproduction fidelity and baseline qualification;
it does not prescribe the candidate's improved method. Existing historical graders
and the pilot's paper attempts retain their scoped calibration role and are not
automatically qualified reproductions.

The [paper catalog](../../benchmarks/catalog/paper.md) reports **117 current paper
contracts: 21 source-grounded designs, 87 unresolved source comparisons and nine
ineligible papers, with zero improvement-ready tasks**. SMC-RNN is a new initial
registration; all 116 earlier paper records and their historical definitions
remain preserved. Contract coverage establishes neither a qualified comparator nor
an empirical win. These are the existing improvement-contract dispositions, not a
count of reproduction-outcome support. Their objective, schema and historical pins
remain unchanged while per-task reproduction proposals are reviewed. Use `status`
for current counts as source preparation and baseline work develop.
The [improvement guide](../science/paper-improvement/README.md) describes the
comparison rule; the [next-build shortlist](../science/paper-improvement/next-builds.md)
identifies original endpoints and remaining native-baseline work.

All **118 neural definitions** now bind versioned understanding contracts while
preserving their exact historical definitions. The current
[neural catalog](../../benchmarks/catalog/neural.md) records **13 delivered named
scopes, 94 partial deliveries, seven designs and four target mismatches**. These
are source-scope dispositions, with no scientific qualification conferred by the
revision. `neural-contract TASK_ID` gives the target, observation limits, evaluation,
controls and missing requirements.

Native neural interpretation covers direct observation and typed-viewer conditions.
Neural tool/model building covers tool-assisted investigation, model development
and frozen prediction programmes. These are distinct outcomes with separate
condition records. Available programme source
cannot supply missing observation access, a working viewer or competent
interpretation controls. Each contract identifies the condition its source
actually supports.

The [OpenMIIR support audit for NEURAL-082](../../benchmarks/neural/NEURAL-082/implementations/openmiir-support-v1/README.md)
now establishes a specific design limitation: neither original stimulus version
contains different-composition alternatives sharing the required tempo and meter,
and no distinct excerpts share the exact recorded full-song duration. Equal windows
cannot create the missing different-melody support. This metadata-only negative
finding changes no task target or access mode and contains no EEG or model result.

The [NEURAL-096 Set–Go preparation](../../benchmarks/neural/NEURAL-096/implementations/full-set-go-v1/README.md)
retains 81,311 spikes from all 204 nominal-800-ms source training/validation trials
and all 54 released units. Raw timestamps, 20 phase bins, actual exposure durations,
six observation segments and three empty support cells are preserved. It supplies
an observation packet; the full-trajectory contrast, nuisance controls, independent
reference, defensible blocked uncertainty and participant delivery remain missing.
The historical 177-trial pre-Set scorer remains a different target. No model,
contrast estimate or scientific qualification follows from this preparation.

## Original paper preparation

The [SMC-RNN original MC_Maze route](../../benchmarks/paper/PAPER-SMC-RNN-2024/implementations/source-matched-nlb-v1/README.md)
prepares all 2,869 original trials and 182 neurons at 20 ms. Validation has 1,721
training and 574 evaluation trials; test has 2,295 training and 574 evaluation trials.
The historical source-only export contains 56 files totaling 27,828,070 bytes.
The separately [verified version2 material pair](../../benchmarks/paper/PAPER-SMC-RNN-2024/docs/official-assets-materials-v2-20261117.json)
contains 71 files totaling 31,393,479 bytes; only the assisted condition includes
the ten released model/configuration/history assets. These are external prepared
payloads, not files published in the receipt, and no participant episode ran.
Both complete author predictions and four-metric aggregates are now recorded in
the [author calibration report](../science/smc-author-calibration-20261117.md).
The noncausal aggregate was accepted as recovered reference output while its
supervisor remains failed. The separate
[later bounded rescore](../science/smc-historical-rescore-20261120.md) succeeded for
both frozen predictions without repeating author-model inference. Exact paper linkage, participant runtime enforcement,
matched budgets and scientific reproduction/improvement qualification remain
separate requirements. The original test targets are publicly exposed; local
separation does not create an untouched holdout.

The [REVE PhysioNet route](../../benchmarks/paper/PAPER-paper-method-003/implementations/original-physionet/README.md)
authenticated all 654 original EDFs across 109 participants and prepared 9,837
epochs under the pinned released-code preprocessing profile. Complete-test-event
constant-output scorer controls passed; that preparation report contains no
model inference. The later [CPU compatibility check](../../benchmarks/paper/PAPER-paper-method-003/implementations/matched-reference-v1/CPU_PROFILE.md)
exercised authentic training updates and exact checkpoint/logit reload, but its
8.51 GiB peak child RSS exceeded the selected 8 GiB ceiling. Overall qualification
failed; no full fit, validation/test predictions or scored paper metric followed.
Its memory measurement is not a full-fit resource estimate. The released direct
200-Hz preprocessing differs from the paper's 128-Hz intermediate description,
and the original downstream classifier checkpoint, PhysioNet training recipe and
seed/run aggregation remain unresolved.
The [sanitized preparation report](reve-source-preparation-20261116.json) records
the source identities, panel accounting and software-control scope separately from
current source bindings; `evidence PAPER-paper-method-003` exposes that report.

The [DeepCaImX source-panel route](../../benchmarks/paper/PAPER-paper-method-013/implementations/source-panel-v1/SOURCE_RECOVERY.md)
authenticated and converted all ten original manual ROI files: 1,563 ROIs across
ten videos from eight donors. Full-panel arithmetic controls exercised segmentation
scoring. Movie-to-mask inference has not run: exact crop/frame mapping,
paper-equivalent checkpoint identity and native assembly remain unresolved. The
[sanitized ROI preparation report](deepcaimx-source-preparation-20261116.json) keeps
the authenticated source and arithmetic-control evidence separate from model
performance; inspect it with `evidence PAPER-paper-method-013`. Its source identity
was reviewed after execution; the control receipt did not capture a contemporaneous
source commit or executable hashes. The
[implementation guide](../usage/implementations.md#prepare-original-paper-endpoints)
links both executable preparation paths and their required boundaries. Neither
preparation result establishes source-paper reproduction or improvement.

## Inventory and execution

The [current registry](../../benchmarks/registry.json) and
[generated catalog](../../benchmarks/catalog/README.md) give current task totals,
implementation ownership and physical paths. The original roster contains 100
paper and 100 neural specifications. The current registry has **235 task entries:
117 paper and 118 neural**. Implementation artifacts are reported separately in the
generated catalog; those source records are not runnable-task or qualification
counts. Expansion registrations, implementation artifacts, historical runtime
declarations and component collections are counted
separately; overlapping counts must not be added together.

Task definitions live at `benchmarks/<track>/<ID>/task.json`. Implementations live
with their task or under [shared source](../../benchmarks/shared/README.md), which
also identifies related-only sources and families without assigned owners.
The [implementation guide](../usage/implementations.md) gives concrete command
routes and their required inputs. An implementation may cover a named endpoint
within a larger task; a task-to-source link does not establish complete execution.

The [source checks](../development/source-integrity.md) verify their declared
ownership, source pins and behavior. Generated controls test software behavior;
authentic-input controls additionally test the declared data path. Model results,
protected evaluation and scientific qualification require their own evidence.
Known gaps include the qualified-imports programme's DMFC dependency, private
scorer inputs for NEURAL-008, NEURAL-023, NEURAL-046 and the historical NEURAL-096
calibration, and the absent historical NEURAL-035 manifest. Consult each task's
current scope before running it.

## Earlier construction reports

The [November 16 source audit](audit-2026-11-16.md) and its
[machine-readable census](audits/2026-11-16.json) preserve the scope and findings of
that review. The [clock arithmetic repair](clock-arithmetic-2026-11-17.md) corrects
comparisons of supplied timestamps; authentic native clock lineage remains open.
The [construction update](construction-2026-11-17.md) and
[source-ownership expansion](expansion-2026-11-17.md) record source additions and
generated checks at their respective revisions. Their historical counts do not
override the current registry or establish new scientific results.

The [provenance index](../provenance/README.md) links earlier releases and execution
reports. The [relocation ledger](../provenance/relocations/2026-11-16.json) records
the original physical moves; later source revisions retain their own lineage.
