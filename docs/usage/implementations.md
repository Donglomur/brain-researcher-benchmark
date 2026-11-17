# Using implementation source

Select the scientific task, outcome and access condition before choosing an
implementation. The [four-outcome design](../design/four-outcomes.md) makes paper
reproduction and improvement, and native neural interpretation and tool/model
building, separate first-class outcomes. A source component may support only part
of one outcome.

Use `paper-contract TASK_ID --outcome reproduction` and `paper-outcomes TASK_ID`
to inspect adopted reproduction contracts, their original-result scope and the
separate improvement/access conditions. `paper-contract TASK_ID` defaults to the
current improvement contract. Read explicit unavailability and unresolved source
limits before choosing an implementation; a retained secondary endpoint cannot
satisfy a different primary finding. Historical calibration adapters, new-split
extensions and source presence do not qualify either outcome. The
[current improvement guide](../science/paper-improvement/README.md) describes the
delivered comparison path.

Start with a task page in the [paper](../../benchmarks/paper/README.md) or
[neural](../../benchmarks/neural/README.md) track. Its definition and source bindings
identify available implementations, shared programmes, current guidance and
remaining limits. The [registry](../../benchmarks/registry.json) records these
relationships; it is not a claim that every registered source package is ready to run.

```sh
python3 -I -S -B scripts/neurobench.py show NEURAL-077
python3 -I -S -B scripts/neurobench.py evidence NEURAL-077
python3 -I -S -B scripts/neurobench.py neural-contract NEURAL-077
python3 -I -S -B scripts/neurobench.py show PAPER-FIND-050
python3 -I -S -B scripts/neurobench.py implementations PAPER-FIND-050
python3 -I -S -B scripts/neurobench.py paper-contract PAPER-FIND-050 --outcome reproduction
python3 -I -S -B scripts/neurobench.py paper-outcomes PAPER-FIND-050
```

Run these metadata commands from the repository root. A task may have retained
predecessors, alternate scientific scopes or several implementation components.
The compact `implementations` view resolves current package paths, roles and scope
limits, including programmes without a legacy runtime registration. Assigned
implementations and related scientific sources are listed separately. `show`
includes the same view alongside the task definition. These commands inspect
metadata without importing implementation code or opening datasets or raw runtime receipts.
The selected public reports shown by `evidence` retain their reported conditions,
metrics and limits; they do not qualify the currently checked-out runtime.
Use the package matching the selected task contract and access condition; ownership
alone does not select a new scientifically preferred route. The
[shared-source index](../../benchmarks/shared/README.md) distinguishes multi-task
programmes, related-only sources and families without an assigned task owner;
location in that directory does not create a task binding.

## Inspect EEG and sleep inputs

The [common operator route](../operator-routes.md) supports NEURAL-077's complete
400-trial EEG development panel and NEURAL-007's complete 5,450-epoch sleep
development panel, each from two previously exposed people. Start with source
discovery:

```sh
python3 -I -S -B scripts/neurobench.py operator routes
```

For input inspection, set `EXTERNAL_DATA_ROOT` to the provisioned asset root and
`EXTERNAL_EVIDENCE_ROOT` to an existing operator-controlled directory outside the
checkout. The example creates a new `inspect-eeg` directory:

```sh
python3 -I -S -B scripts/neurobench.py operator inspect NEURAL-077 \
  --data-root "$EXTERNAL_DATA_ROOT" \
  --output "$EXTERNAL_EVIDENCE_ROOT/inspect-eeg"
```

Use `NEURAL-007` and a fresh output directory for sleep. For an existing lifecycle
packet, point the data root at its `inputs/` directory and add `--layout prepared`.
Inspection authenticates the complete public allowlist against the packaged pins;
it does not open development targets or run a model. It does not download missing
data or accept arbitrary recordings from the same study.

The operator guide gives the preparation, frozen-programme and Docker grading
commands. Grading requires explicit artifact locations, the preinstalled native
image and a mandatory purpose (`development-control` or `model-evaluation`). A
purpose label does not replace method provenance, protected evaluation or scientific
qualification. Preserve both successful and failed outputs outside the checkout.

## Separate the question from the access condition

For paper tasks, select reproduction or improvement, then paper + data or paper +
data + author code. Inspect the selected contract and `paper-outcomes TASK_ID`
before choosing a scorer. Each outcome has its own criteria; success in one does
not establish the other. An `unknown` cell or a passing metadata/source check is
not a completed scientific benchmark. The historical paper
`score` and `run` routes still require `--calibration`; their outputs cannot establish
the current improvement objective or automatically qualify AI reproduction. Improvement
candidates may change architecture, inference or optimization while preserving
the contract's permitted observations,
cohort, split, evaluation, required controls and resource budget. The author-source
recipe defines the baseline comparison.

For neural tasks, distinguish direct interpretation without arbitrary analysis
tools, interpretation through a restricted typed image-navigation viewer, and
agent-built tools, models or programmes. Use the specific condition named by the
current definition; a viewer is a tool-mediated observation condition, while a
programme may include agent-created analysis or learning code.
`neural-contract TASK_ID` reads its pinned `understanding.v1.json`, including the
target, permitted observations, controls, source delivery and missing requirements.
Prepared feature inputs, raw waveforms and rendered images expose different
information. A prediction-programme result cannot be reported as direct or viewer
interpretation. The [NEURAL-007 and NEURAL-077 pilot](../science/difficulty-pilot-20261117.md)
contains programme attempts on exposed development people; the separate NEURAL-077
[waveform](../../benchmarks/neural/NEURAL-077/implementations/complete-direct-condition-v1/EVIDENCE.json)
and [viewer](../../benchmarks/neural/NEURAL-077/implementations/visual-viewer-v1/EVIDENCE.json)
reports describe software controls without model evaluation.

The [restricted viewer transport](../../benchmarks/neural/NEURAL-077/implementations/visual-transport-v1/README.md)
connects the typed viewer to a fresh local participant process for each query.
Its authentic 400-query scripted collection is complete and unscored; 15 boundary
checks exercise local denials and response handling. No model was called, and a
remote provider's image delivery, capacity and context isolation remain unqualified.
The guide separates zero-shot and four-demonstration conditions and preserves
failed sessions; neither condition includes evaluator feedback.

The [whole-night sleep viewer](../../benchmarks/neural/NEURAL-007/implementations/whole-night-viewer-v1/README.md)
provides observations for every one of the 5,450 development epochs. Typed actions
show waveform images and permitted clock metadata, with past and future navigation
within the current person, no labelled demonstrations and no evaluator feedback.
The [historical scripted preparation, delivery and replay](../science/sleep007-viewer-delivery-20261117.md)
completed under renderer source `1c9357d1`, using fixed uniform responses without
an AI participant or scientific score. The later renderer correction `39a1f84c`
has generated-only evidence and does not inherit that authentic execution proof.
Restricted provider transport, participant isolation and model performance remain
unqualified. The canonical unsupported direct/viewer mode is unchanged.

The sleep feature programme can learn from six training people's labels; the
whole-night viewer is zero-shot and exposes raw waveform images plus clocks.
These are distinct information budgets. The same task, person or query IDs permit
a scoped capability comparison but cannot by themselves isolate an
information-matched effect of tool access.

For NEURAL-082, the [OpenMIIR source-support command](../../benchmarks/neural/NEURAL-082/implementations/openmiir-support-v1/README.md)
authenticates the original metadata and enumerates all 66 stimulus pairs in each
version without EEG or audio acquisition. It finds no different-composition pair
sharing the required tempo and meter. Song identity or vocal/instrumental rendition
classification would change the scientific target; neither is activated as a
substitute. This is a source-design audit, not a neural scorer or model failure.

The [NEURAL-096 full Set–Go route](../../benchmarks/neural/NEURAL-096/implementations/full-set-go-v1/README.md)
uses `prepare.py` on the exact pinned source NWB to retain all 204 nominal-800-ms
training/validation trials, 54 units and 81,311 native spikes in half-open [Set, Go)
intervals. It preserves raw timestamps, phase counts and actual bin exposures;
it does not fit a trajectory or compute a prior contrast. Six observation segments
are not authenticated randomized-assignment blocks, and three empty support cells
cannot be dropped to manufacture uncertainty. The saved-packet audit recounted
prepared timestamps, not the original NWB spikes; the 14 additional unit identities
were not independently recovered. The full scientific contrast and participant
modes remain undelivered, separately from the historical pre-Set calibration.

## Prepare original paper endpoints

These additive routes implement concrete source preparation and scoring steps.
Their software and data evidence is separate from a reproduced author model or a
candidate improvement. Reserve the required acquisition, disk and native resources
before running them; data, targets, checkpoints and outputs stay outside public Git.

| Task and route | Executable source and observed coverage | Remaining comparison requirements |
| --- | --- | --- |
| [SMC-RNN / PAPER-SMC-RNN-2024](../../benchmarks/paper/PAPER-SMC-RNN-2024/implementations/continuous-outcomes-v2/README.md) | Current `prepare`, `inspect`, `freeze` and `score` source preserves the original MC_Maze 20-ms panel: both source methods' eight reproduction findings and one offline candidate's four metrics, with reference discrepancies. Access conditions compare paper/data against the same materials plus pinned official code and ten released model/configuration/history files. [Author calibration completed](../science/smc-author-calibration-20261117.md) both full prediction arms at 192 particles × 32 repeats and both four-metric aggregates. | Fresh current materials and runtime boundaries remain to be validated. Reports are continuous fixed-panel measurements, not binary reproduction or improvement decisions. The failed noncausal supervisor and independently accepted recovered scalar output remain distinct; calibration is not an AI outcome. Released models do not establish exact historical training exposure or checkpoint-to-paper identity. |
| [REVE / PAPER-paper-method-003](../../benchmarks/paper/PAPER-paper-method-003/implementations/original-physionet/README.md) | `panel.py acquire`, `inspect`, `prepare`, `predict` and `score`; all 654 official EDFs for 109 participants prepared into 9,837 epochs, preserving the 1–70 / 71–89 / 90–109 train/validation/test split | Released-code and paper filtering recipes disagree; the exact downstream classifier checkpoint, historical run aggregation and author-model performance remain unresolved. No model inference ran. |
| [DeepCaImX / PAPER-paper-method-013](../../benchmarks/paper/PAPER-paper-method-013/implementations/source-panel-v1/SOURCE_PANEL.md) | `source_panel.py convert-rois` and `score-segmentation`; all ten original manual ROI files authenticated and converted, preserving 1,563 masks and spatial coordinates | Exact movie crop/frame mapping, paper-equivalent full checkpoint and native assembly are unresolved. Ten videos correspond to eight donors. No movie-to-mask inference ran; segmentation arithmetic alone leaves trace/runtime obligations open. |

For the retained SMC-RNN author routes, keep the two environments separate: original NWB preparation uses
Python 3.9 and pandas 1.3.4; Python 3.11 with pandas 1.5.3 is the separate inference
environment and reads already-frozen HDF5 inputs only. Preparing the NWBs with
pandas 1.5.3 truncated original trial support and is retained as a failed attempt.
The full native `panel.json` and smaller public `reference_panel.json` have
different hashes because the latter is a metadata subset of the same frozen input
panel; that difference does not indicate changed trials or arrays.

Use the [current SMC continuous interface](../../benchmarks/paper/PAPER-SMC-RNN-2024/implementations/continuous-outcomes-v2/README.md)
with the exact adopted task identity for a fresh paired export. The assisted
condition adds official source and the ten allowlisted released assets; it measures
code and pretrained-asset assistance together. The source-only v1 condition remains
historical and must not be relabelled as v2. Both conditions keep the original inputs
and matched per-outcome resource profiles. Supplied validation behavior may guide
fitting or selection only under the declared policy; actual usage is reported.
No original test target or operator prediction is delivered. Reproduction freezes
both source-method arms together; improvement freezes one complete offline
prediction set using the full 35-bin held-in window. Original metrics and reference
differences are reported without new equivalence thresholds or binary wins.

The retained [source-matched SMC routes](../../benchmarks/paper/PAPER-SMC-RNN-2024/implementations/source-matched-nlb-v1/README.md)
and [paired-delivery guide](../../benchmarks/paper/PAPER-SMC-RNN-2024/implementations/source-matched-nlb-v1/DELIVERY.md)
document author reproduction and calibration. Their
[preparation evidence](../../benchmarks/paper/PAPER-SMC-RNN-2024/docs/source-preparation-evidence.json)
records an earlier complete paired export, excluding checkpoints, operator
predictions and test targets. That receipt does not qualify a new code-and-weights export
or candidate run. Both source-author arms now have authenticated [calibration
results](../science/smc-author-calibration-20261117.md), with the failed noncausal
supervisor and recovered scalar output preserved. Current reports retain the SMC
references and the paper's complete LFADS/NDT vectors separately; exceeding SMC
alone does not establish a gain over the paper's strongest published comparison.
Strict-online and source-prefix candidates need separately named information
policies and appropriate comparators. The source causal arm's reflect-padding
startup is not strictly online.

The REVE guide gives the acquisition, complete-panel preparation, frozen prediction
interface and evaluator commands. Its predictor receives signal shards and channel
names without targets, but Python adapters are trusted operator code: untrusted
candidate execution requires a separate isolated input view. A pretrained encoder
cannot substitute for the missing downstream classifier head. Keep final targets
out of preprocessing, checkpoint and hyperparameter selection.

The [DeepCaImX recovery report](../../benchmarks/paper/PAPER-paper-method-013/implementations/source-panel-v1/SOURCE_RECOVERY.md)
also provides checkpoint inspection and bounded source-range inspection. These
inspectors identify released artifacts and physical storage; they cannot establish
the missing movie-to-reference transformation. The scorer retains strict IoU > 0.5,
ten-video macro F1 and unresolved matching/SD conventions explicitly. Public upstream
annotations and targets remain historically exposed even when local evaluator
files are separated.

Candidates may change architecture, inference or optimization within the task's
permitted observations, evaluation and budget. The source-author recipe and
checkpoint requirements above concern author-baseline qualification; they do not
require candidates to copy the author method.

## Portable programme sources

The following published packages retain explicit complete-programme scopes and
source-check interfaces. Their actual inputs, protected evaluation, native
execution and scientific qualification have separate requirements.

| Package | Preserved scope | Required beyond source checks |
| --- | --- | --- |
| [NEURAL-029](../../benchmarks/neural/NEURAL-029/implementations/neural029-programme/README.md) | Complete registered GrC1s-to-2s calcium transfer: all required pairs, cells, query trials and 61 times, with the accepted frozen-program boundary | Complete admitted public/private packet, NumPy grader, qualified Docker environment, capacity and outside observation |
| [NEURAL-030](../../benchmarks/neural/NEURAL-030/implementations/neural030-four-cell/README.md) | All 16 cerebellar sessions, four input arms and two agent modes: 128 dispatches | Authentic MAT extraction and five-mouse/clock binding, complete public/private packets, adaptive agent and native environment qualification |
| [NEURAL-078](../../benchmarks/neural/NEURAL-078/implementations/neural078-deferred-grade/README.md) | Full eight-person EEG reconstruction, all 195 report fields and protected grading after producer closure | Admitted authentic collection/reference export, frozen programme, trusted outside observation and native grading qualification |
| [NEURAL-061](../../benchmarks/neural/NEURAL-061/implementations/neural061-persistent-state/README.md) | 423 source sessions, 29 evaluation sessions, six references, ten seeds and both BR/BC arms; persistent fitted state remains in its isolated child | Authentic inputs/targets, qualified native environment, provider/capture/allocation provenance and independent outside observation |
| [CBraMod / PAPER-paper-method-024](../../benchmarks/paper/PAPER-paper-method-024/implementations/cbramod-paired-program/README.md) | 12 datasets; 800 reproduction artifacts, 60 improvement cases and 420 comparator slots per condition | All 65 exact external official-code files, authentic data/reference lineage, native execution and 8GB output capacity qualification |
| [PAPER-FIND-050](../../benchmarks/paper/PAPER-FIND-050/implementations/paper-find050-programme/README.md) | Critical initialization: 26 operations, 40 complete 10,000-mode spectra, 29 main sessions and a separate prospective memory endpoint | Exact external official source, authentic inputs and all 32 scientific/runtime gates, including live-issuer and full-capacity qualification |

These source scopes preserve their declared populations and comparison conditions.
They do not establish broad paper reproduction, neural understanding, improvement
or an increased completed-benchmark count.

## Current package roots

Some package READMEs preserve their original release text, including commands that
use the former directory layout. From the repository root, select
the matching current `PKG` assignment below before following the package's command
sequence. The [current portable-source workflow](../../.github/workflows/portable-benchmark-source.yml)
provides the selected verifier commands and source pins for this layout.

| Package | Current shell assignment |
| --- | --- |
| NEURAL-029 | `PKG=benchmarks/neural/NEURAL-029/implementations/neural029-programme` |
| NEURAL-030 | `PKG=benchmarks/neural/NEURAL-030/implementations/neural030-four-cell` |
| NEURAL-078 | `PKG=benchmarks/neural/NEURAL-078/implementations/neural078-deferred-grade` |
| NEURAL-061 | `PKG=benchmarks/neural/NEURAL-061/implementations/neural061-persistent-state` |
| CBraMod / PAPER-paper-method-024 | `PKG=benchmarks/paper/PAPER-paper-method-024/implementations/cbramod-paired-program` |
| PAPER-FIND-050 | `PKG=benchmarks/paper/PAPER-FIND-050/implementations/paper-find050-programme` |

These assignments select physical directories. Historical source prose remains
bound to its original revision; embedded capsule names, manifest member names,
logical identifiers and historical pins retain their declared meaning. Do not
replace those identifiers merely because a directory moved. Use the current root
and current CI binding for execution, and preserve the package's input, environment
and admission requirements.

## Check source before execution

Use a trusted, reviewed revision. Each package's guide describes its own source
inventory, verifier and control commands. Authenticate a verifier against the
reviewed release or current CI binding before executing it; a verifier cannot
establish trust in its own bootstrap. The
[portable-source workflow](../../.github/workflows/portable-benchmark-source.yml)
records its selected packages and commands. Per-package counts, pins and environments
belong to that exact revision, rather than a duplicated checklist on this page.

The [repository ownership and source-integrity checks](../development/source-integrity.md)
have distinct scopes: the first covers the artifact ownership and layout declared
in the [current registry](../../benchmarks/registry.json); the second verifies recorded
source pins for four enrolled bundles. Passing either
does not supply missing dependencies or native qualification. Generated source
controls are software evidence, not authentic-data or model results.

## Prepare an actual run

Read the implementation's required input schema, external code dependencies,
interpreter/environment, resource envelope and producer/evaluator separation.
Authentic recordings and protected references may be external. Some packages also
retain unavailable source dependencies: the qualified-imports programme lacks its
required DMFC engine; several registered neural scorer bridges require private
inputs; NEURAL-035 lacks its historical manifest. Read the affected task's registry
notes before selecting an implementation. A nearby implementation is not an
interchangeable substitute. Package-local licenses and attribution notices
continue to apply after relocation.

For existing finished-submission routes, see [artifact grading](artifact-grading.md).
For a controlled paper or neural comparison, use the [study-design guide](../science/study-design/README.md)
and bind its complete endpoint and access conditions before collecting outcomes.
The generic `run` and `score` commands retain their own admission checks. For a
revised neural contract whose source evaluates a different target, has no target
evaluator, or has unresolved target fidelity, these commands require explicit
`--calibration` before reading a submission or candidate. A verified historical
adapter cannot establish success on the current neural target. Inspect
`neural-contract TASK_ID` for its exact scope; calibration does not bypass runtime
verification. Campaign
commands refuse execution without explicit `campaign_authority` and the required
private inputs. A source binding or successful metadata query does not enable
execution automatically. Delivery exports are local generated files under the
ignored `.neurobench/exports/` directory.
