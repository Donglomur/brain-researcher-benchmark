# PAPER-FIND-REP-003 initial evaluator v1

This package implements a complete **normalized-artifact scoring component** for joint-angle decoding against a train-only movement-phase comparator, plus a separate optogenetic contact-timing component. The scorer does not load native MAT files or fit neural models; the separate read-only native clock audit below admits one optogenetic file. It is not a completed or scientifically qualified benchmark. The canonical task, historical registrations, full population, intervention trajectory endpoint, native-reference and protected-evaluation gates remain intact.

## Source and prospective policy

The canonical task SHA256 is `6158f36058f07a4112a70cbca57d13e26fcfe9ce61a2384ba4f44f0c8de12a36`. The paper is [eLife 106270.3](https://doi.org/10.7554/eLife.106270.3); the inspected primary article XML is [the publisher's VoR XML](https://cdn.elifesciences.org/articles/106270/elife-106270-v1.xml), whose article-version DOI explicitly identifies `.3`. The filename's `v1` must not be interpreted as paper version 1. Author code is [GSK26-public at 815b610b3beddfed5a3abf611d3a465ab9e4ce5c](https://github.com/kaufmanlab/GSK26-public/tree/815b610b3beddfed5a3abf611d3a465ab9e4ce5c). Exact file hashes and semantic mappings are in `implementations/initial-evaluator-v1/provenance.json`.

The inspected `cvRegress.m` computes `1 - var(actual - prediction) / var(actual)`. This source **VE** differs from squared-error R²: an otherwise perfect prediction shifted by a constant still has VE 1. The component reports both source VE and a separately named R² diagnostic. It rejects constant held-out targets because source VE is undefined; it never silently removes joints. Floating-point overflow, missing predictions and malformed arrays also fail.

The source's parameter names are misleading: `decode.m` passes `nPartitions=10,nFolds=5`, and `cvRegress.m` loops using modulus 10. Its actual design, also described by the primary paper, is **five repetitions of ten-fold whole-trial partitions**. The component requires explicit protected split assignments, balanced held-out fold sizes and all trials exactly once per repetition. It does not claim to reproduce MATLAB `rng(240926)`. Frames from one trial cannot cross a train/test split.

The prospective comparator averages training joint-angle trajectories separately for left and right trials at each of the 51 event-relative time bins. It predicts held-out movement from direction and time alone. This differs from the author's residual-decoding analysis, which subtracts all-trial left/right means. The component does not silently replace that source analysis. The contrast is neural prediction VE minus this train-only phase-template VE, computed per joint on concatenated held-out frames. A fold's contrast is the median across all 24 joints. A session's contrast is the mean across all 50 fold models. These aggregation and comparator choices are an explicit prospective policy, not a source numerical reconstruction or a binary grading target.

The two sessions per mouse remain paired. Across mice, the evaluator gives equal weight to each of the five mice and reports M1, S1, and paired M1-minus-S1 phase advantages. Its exhaustive two-sided sign-flip test uses 32 assignments under sign exchangeability; its exhaustive animal bootstrap uses 3,125 five-mouse resamples and linear percentile endpoints. These are descriptive prospective summaries, not evidence of independent-animal generalization. Repeated folds and adjacent frames do not increase the animal sample size. With five identically positive effects, the smallest two-sided sign-flip p-value is 0.0625.

The source applies PCA before trial CV, with retained dimension 90% of included neuron count, and selects the top 100 lift-modulated cells. This component performs neither operation; submitted-prediction provenance and train-only versus source-transductive modeling remain external qualification gates. It cannot infer a leak-free model from good predictions.

## Normalized decoding interface

Use Python 3 with NumPy; no installation or network access occurs. From the repository root:

```sh
python3 benchmarks/paper/PAPER-FIND-REP-003/implementations/initial-evaluator-v1/evaluator.py decode /absolute/protected-reference.json --submission /absolute/predictions.json --output /absolute/report.json
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s benchmarks/paper/PAPER-FIND-REP-003/implementations/initial-evaluator-v1/tests -v
```

Reference JSON has `schema_version: 1`, `task_id: "PAPER-FIND-REP-003"`, `source_revision` equal to the commit above, and `artifact_kind` either `generated_engineering_control` or `normalized_empirical_unqualified`. The latter is an honesty label, not empirical admission. It also contains exact `joint_names` and `time_ms` lists exported as `JOINT_NAMES` and `TIME_MS` by the evaluator, and `sessions` as follows:

- Each session object has `mouse`, six-digit `session`, `region`, `neural_trials`, `kinematic_trials`, and `folds`.
- A neural metadata record has positive integer `trial_number` and binary `locked`. A kinematic record has the same keys plus `LR: "L" | "R"`, `joint_angles` with shape 51×24, and `eligibility`.
- `eligibility` contains all native selection fields: `success`, `grabTimeC`, `liftRT`, `goodDLC`, `wrongZoneFirst`, `movementTime`, `timeToContact`, and `has_radical`. Only `grabTimeC` may be null, explicitly representing a missing source contact. Other missing/nonfinite fields fail rather than being silently discarded. Binary fields admit booleans or integers 0/1. Numeric strings and booleans in continuous arrays are rejected.
- `folds` contains exactly the 50 `(repeat, fold)` pairs from `0..4 × 0..9`. Each has `train_trials` and `test_trials`, which partition the full eligible population, have no duplicate or overlapping trial IDs, and leave both left and right directions in training.

The exact imaging sessions are:

| Mouse | M1 | S1 |
|---|---|---|
| cfa17 | 200825 | 200827 |
| cfa19 | 200820 | 200826 |
| cfa20 | 201114 | 201118 |
| cfa22 | 220605 | 220611 |
| cfa24 | 220727 | 220724 |

All ten are mandatory. Trial IDs are unique **within session**, never treated as globally unique. Neural and kinematic metadata are joined by ID, not row order; their complete identity sets and lock flags must agree. Selection follows `loadLock4Decode.m`: success, observed grab time, liftRT < 500, goodDLC, no wrong zone first, movementTime < 500, timeToContact < 1000, and has_radical. Both modalities must be locked. Exclusion reasons and eligible counts are emitted. A native importer must supply the entire declared session inventory, including excluded records, and independently demonstrate completeness; a self-consistent JSON artifact alone cannot prove this. Requiring has_radical preserves the source selection even for smoothed-deconvolution predictions.

The field is `jointAngles`, with the 24 author-defined joints in exact `loadData.m` order; time is `-100:10:400` ms relative to `liftTimeDLC`. Inputs must already share the source's clock, smoothing and joint-angle units. Values are not reinterpolated, rescaled or pose-estimated. Source array extraction and units remain unqualified until a native bridge is audited.

Submission JSON has `schema_version`, `task_id`, and `predictions`. Each prediction has `mouse`, `session`, `repeat`, `fold`, `trial_number`, and `joint_angles` (51×24). The set must equal every protected held-out identity exactly: no extras, duplicates, row-position joins or omissions. A reference and submission can be generated in memory by `tests/test_evaluator.py:fixture`; that fixture is explicitly generated engineering data. The CLI rejects duplicate JSON members and nonstandard NaN/Infinity constants, and records SHA256 of the exact reference and submission bytes.

The reference belongs to the operator: it includes targets, split assignments and training trajectories. Candidate access packets must independently withhold protected targets and comply with the canonical paper-only versus paper-plus-official-code conditions. This package does not provision those packets or authorize candidate access to the reference.

## Separate optogenetic timing interface

```sh
python3 benchmarks/paper/PAPER-FIND-REP-003/implementations/initial-evaluator-v1/evaluator.py opto /absolute/opto-reference.json --output /absolute/opto-report.json
```

The reference has the same top-level schema/task/revision/artifact-kind fields and an `opto_trials` list. Each record requires `mouse`, explicit `session`, positive `trial_number`, `success`, `optoProblem`, `optoTrial`, `grabTimeC`, `liftTimeC`, and `wrongGrabFirst`. Contact/lift may be null to represent missing source event times; these records are excluded. Both `cfaVG1` and `cfaVG4` must occur, with selected control and stimulation trials for each mouse. These are separate optogenetic mice: no neural-imaging trial join is invented. Normalized inputs alone do not prove native completeness; the audit below verifies identity and completeness for the exact pinned `optoData.mat` release.

The source Figure 1H selection is successful trials without opto problems or wrong-first grabs, with grabTimeC > liftTimeC, separated by optoTrial. The plotted value is **grabTimeC / 1000 seconds**, with no origin subtraction. The source labels zero as cue, but the native release does not establish that this field is already cue-relative; see the clock audit below. Source `linspace(0,9,30)` gives 30 edges and 29 bins. The final right edge is inclusive. Probability divides by **all selected observations**, retaining outside-window mass in the denominator. Counts, probabilities, selected counts, outside-window counts and excluded trial keys are reported. The additional per-mouse mean timing difference and equal-mouse mean are explicitly prospective descriptive summaries conditional on this success selection. They do not establish a causal intervention effect. Detailed trajectories and Figure 1I remain unimplemented, and source Figure 1I's single-mouse example is not generalized to the entire intervention population.

## Native optogenetic clock audit

`implementations/initial-evaluator-v1/native_clock_audit.py` independently admits the complete pinned `optoData.mat` and checks its identity and clock lineage. It is a read-only provenance audit, separate from native delivery and scoring. Python 3 with SciPy is required; no dependencies are installed. Its receipt contains population and clock summaries, with no normalized trial records, selection labels, histograms or endpoint targets:

```sh
python3 benchmarks/paper/PAPER-FIND-REP-003/implementations/initial-evaluator-v1/native_clock_audit.py /absolute/optoData.mat --output /absolute/new-admission.json
```

The admitted file is Figshare article 28326998 version 1, file 60332969, 9,351,260 bytes, SHA256 `9d2be90908a05684dff9871697f5c37bb4f93522af67bf2625219f12cb4fd19c`. The audit verifies this exact identity before parsing the same bytes, the sole `optoData` struct's 1×3304 shape and sixteen fields, and every `(animalID, date, trialNumber)` key. All 3,304 trials are retained, including failures and missing events, across the two mice and eight full session timestamps. `date` is retained as `YYYYMMDD_HHMMSS`; reducing it to a six-digit imaging-session date would change native identity. The expected session roster and each session's complete trial-number range are checked independently of row order.

The millisecond units are consistent with the author's `/1000` conversion. On all 2,947 rows with finite events, `grabTimeC - waterTime == grabRT` and `liftTimeC - waterTime == liftRT` exactly, and `waterTime` is nonzero. Each event and RT field has 357 missing values; `waterTime` has two. Missing events remain part of the admitted population. Malformed scalar types, infinite values, missingness inconsistencies and clock-identity failures are rejected even on failed trials.

This matters scientifically: the paper describes cue and water delivery as simultaneous, while pinned [`preproc/loadEventTimes.m`](https://github.com/kaufmanlab/GSK26-public/blob/815b610b3beddfed5a3abf611d3a465ab9e4ce5c/preproc/loadEventTimes.m#L22) subtracts `waterTime` to obtain contact reaction times. In contrast, `plotOptoHists.m` plots the unshifted `grabTimeC` field and labels zero as cue. Thus the source-code transform and a water/cue-relative latency are distinct on the released data. The native timestamp's absolute origin and the source plot's cue interpretation remain unresolved. No reanchoring is applied, no alternate endpoint is scored, and the existing evaluator, canonical task and numeric outputs are unchanged. Legacy evaluator names containing `cue` do not resolve this discrepancy.

The audit always reports `cue_clock_interpretation_validated: false`, `scientific_qualification: false`, and `full_contract_complete: false`. [Native clock provenance](../implementations/initial-evaluator-v1/native-clock-provenance.json) records exact data/source pins and remaining conditions. Authentic population admission and these clock identities do not qualify the neural decoder, trajectory analysis, article statistics or scientific task.

## Evidence and limits

Generated controls establish exact source-metric arithmetic, full-population and trial-join checks, phase-template train isolation, balanced whole-trial folds, five-mouse inference, and optogenetic selection/transform/bin semantics. The additional native audit establishes only the pinned population and clock facts above. Neither establishes baseline competence, native MATLAB parity, meaningful benchmark difficulty or scientific qualification. Scorer outputs retain `scientifically_qualified: false` and `full_contract_complete: false`.

The pinned code's `LICENSE` is CC0 1.0; the canonical Figshare metadata records CC BY 4.0 for data. This implementation redistributes neither recordings nor full author source/paper content. Paper/data/code exposure, attribution and downstream artifact terms remain applicable. The original generated scorer controls used no native data. The later admission audit read the already acquired 9.35 MB native MAT only; no fitted model, package installation, solver trial or paid/model API was used.
