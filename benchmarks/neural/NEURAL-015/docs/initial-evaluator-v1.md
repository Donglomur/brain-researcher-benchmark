# Complete-cohort word-onset grid evaluator

This package implements an independently useful scoring and preparation path for
NEURAL-015: strict cohort and fold validation, target-free query grids, tolerance
labels, participant-macro average precision (AP), paired incremental log loss,
class-balance and latency-shift diagnostics, participant uncertainty, and a
source-informed trigger conversion. It is construction code, with generated
engineering controls. Scientific qualification remains **unknown**; every report
has `admitted: false`. It neither executes nor claims a neural reference baseline.

The immutable task is `task.json`, 28,703 bytes, SHA-256
`0defdcc095905ddb5186f2b0de0861ba2d527bb25a449bffa777b622e69f204c`.
No canonical definition, historical artifact, or admission state was changed.

## Source versus prospective policy

The [Brain Treebank paper](https://arxiv.org/html/2411.08343v1) provides word-onset
annotations, recordings and author analyses. Its Appendix A.9 analyzes balanced
sentence-onset versus nonspeech epochs with ROC-AUC. That experiment does not
define this benchmark's fixed-grid word-boundary AUPRC or person/movie transfer
protocol. The registered task does define participant-macro boundary AUPRC and
incremental log loss over acoustic/visual controls.

This package therefore names its profile `prospective-onset-uniform-grid-v1`.
Here “boundary” means **every word start**, including non-sentence-initial words;
it excludes word offsets. Grid spacing, tolerance, clipping, lag support, shift,
bootstrap seed and draw count have **no hidden defaults**. They must be frozen
in the private reference before outcomes. This is a justified implementation
policy, not a historical author convention or an approved scientific protocol.

The version-pinned author source is commit
`c54ba38eab7814538bc03b1b6d29a3f50f034e12`. Its
[clock reader](https://raw.githubusercontent.com/czlwang/brain_treebank_code_release/c54ba38eab7814538bc03b1b6d29a3f50f034e12/data/trial_data_reader.py)
uses the nearest trigger plus 2048 Hz interpolation and rounding. Its
[trial reader](https://raw.githubusercontent.com/czlwang/brain_treebank_code_release/c54ba38eab7814538bc03b1b6d29a3f50f034e12/data/trial_data.py)
drops rows with missing values across unrelated transcript features. This package
does not inherit that population reduction. Full word-start extraction and any
missing target starts must be resolved by the operator; omission is not validated
merely because the resulting list is syntactically valid. Source provenance,
Git object pins and requirements mapping are in `provenance.json`. Source bytes
were inspected through primary web sources; direct source SHA-256 acquisition
failed, so Git object pins are explicitly distinguished from content SHA-256s.
No author source is vendored or copied into this implementation.

## Populations, folds and access

`catalog.json` is derived from the task's entire metadata map: 26 recording
presentations, 10 clinical participants, 21 movie identities. IDs have the form
`sub_1_trial000`. Every reference and submission must cover all 26. No convenient
subset or silent missing-record imputation is accepted.

Each fold declares exact `train`, `test` and `unused` recording-ID lists; these
are disjoint and partition the full catalog. Train and test must share neither a
person nor a movie. Every recording appears in test exactly once overall. All
records sharing a person **or** a movie belong to the same test fold, so their
connected components are indivisible. For this catalog, valid minimal joint
components have participant groups `{1,5}`, `{2}`, `{3,4,6,7,10}`, `{8}`, `{9}`.
Larger merged groups are allowed if train remains nonempty. `unused` records are
excluded only from a particular fold's fit, never from total test coverage.

Fitting, preprocessing, normalization, feature selection, hyperparameter
selection and adaptation must use only that fold's training records. Any inner
validation must remain inside train and use the same identity and temporal
restrictions; this scorer cannot inspect an external training program. Frozen
recipe hashes are declarations, not evidence that fitting followed them.
Future neural or context lags are prohibited by this profile. Every declared
lag is nonpositive; the symmetric edge guard is at least the largest absolute
lag. Guarding both edges is a conservative prospective rule. Native array
lengths and true feature support remain independent validation responsibilities.

The query exporter is a strict allowlist: task/profile, a target-free protocol
SHA-256 commitment, recording ID, fold ID, grid start, exclusive grid stop,
step, and number of grid points. It never exports movie
identity, transcript fields, onsets, labels, private source hashes or comparator
probabilities. The grid depends only on declared recording length and fixed
guard/step, never on labels. These IDs still identify a public development
corpus: target-free metadata does not make publicly retrievable labels secret.
The exporter is a grid descriptor, not a neural-payload broker; actual signal
delivery, file access and process isolation remain held.

## Metric definition

For a recording with `sample_count = N`, guard `g` and step `s`, score exactly
the integer sample indices in `range(g, N-g, s)`. The rate is declared 2048 Hz,
based on author source and awaiting native calibration. A bin is positive if
its distance to **any** private word-onset sample is at most the declared
`tolerance_samples`. Inclusive tolerance windows form a union: overlapping or
coincident words never duplicate observations. This is binary fixed-grid
localization, not one-to-one event matching or boundary F1. A very coarse grid
can miss onsets; spacing and tolerance need pre-outcome scientific approval.

Within each participant, all recordings' eligible bins are pooled. AP sorts
probabilities descending, processes equal-probability groups together and sums
`recall_increment * precision_after_group`. It is noninterpolated average
precision, not trapezoidal PR area. Primary natural-grid weights are equal per
bin. Within-participant pooled grid log loss uses natural logarithms and an
explicit probability clip; endpoint clipping counts are reported. Incremental
log loss is `operator_acoustic_visual_loss - neural_loss`, so positive means
the candidate improves on the comparator. The primary endpoint is the
unweighted mean of the ten participant metrics, not a pooled cohort metric or
an equal-session mean. Recording coverage and participant prevalence are kept.

The comparator predictions reside **only in the operator-owned private
reference** and must be frozen with its digest before candidate outcomes.
Entrants cannot submit or replace comparator scores. Its features must come
from independently timed continuous media windows under the same folds.
Deposited word-aligned loudness/motion rows are not acceptable substitutes:
their timestamps, spacing and aggregation windows disclose the target. The
scorer cannot prove comparator provenance, competence or freedom from leakage;
those native/reference holds remain open. Reported input hashes bind contents,
but an operator must retain the prior freeze record to establish chronology.

The task's “balanced timestamp grid” is underspecified. A uniform timestamp
grid is not class balanced. We retain every query bin, avoiding target-dependent
query selection, and additionally report a **diagnostic** that assigns total
weight 0.5 to positive bins and 0.5 to negative bins within each participant.
This is explicitly separate from the natural-prevalence primary metric; the
contract's final balancing interpretation remains a protocol hold.

The latency diagnostic shifts the candidate's probabilities by an integer
number of bins within each recording. Positive shift uses an earlier prediction
at the current target (`prediction[i - shift]`). No circular wrap or crossing
recordings is allowed. Magnitude must exceed tolerance plus maximum feature
lag. Compare unshifted and shifted neural predictions on their identical valid
interior subset and report that subset's count separately. This score does not
replace the full-grid acoustic/visual comparison, and the diagnostic does not
establish a biologically sufficient null under every temporal autocorrelation.

Constant probabilities are accepted and flagged as null controls; constant AP
equals prevalence. Missing/extra/duplicate IDs, mismatched folds, wrong lengths,
NaN/infinity, bool probabilities, unknown fields and values outside [0,1] are
rejected. If a participant has no positive bins, AP and the macro AP become
`null`; the participant is never dropped. With no negative bins AP is 1 but
prevalence and counts expose degeneracy, and the balanced diagnostic is `null`.

Optional percentile bootstrap intervals resample the ten participants with
replacement, using the same sampled people for both arms in every draw. They
operate on participant summaries with a frozen seed and explicit draw count
(`0` disables intervals; the evaluator caps requests at 100,000). They are
descriptive paired participant uncertainty. Clinical selection and repeated
stimuli limit population interpretation; these intervals do not model movie
clusters or training-model dependence and cannot establish population validity.

## JSON interface and commands

Python 3.9+ standard library only; no installation, network request or data
download occurs in the program. All JSON objects reject unknown fields; file
loading also rejects duplicate JSON keys and nonfinite constants. The following
structures are schematic: a real reference needs every catalog entry and full
private arrays, not the one-row ellipses below.

`reference.json` has exactly `task_id`, `protocol`, `folds`, `recordings`.

```text
protocol:
  profile: prospective-onset-uniform-grid-v1
  sample_rate_hz: 2048
  grid_step_samples: positive integer
  tolerance_samples: nonnegative integer
  feature_lags_samples: nonempty list of nonpositive integer sample offsets
  guard_samples: integer >= max(abs(feature_lags_samples))
  latency_shift_samples: nonzero whole grid steps; abs > tolerance + max lag
  probability_clip: number in (0, 0.5)
  bootstrap_draws: integer in [0, 100000]
  bootstrap_seed: nonnegative integer
  fitting_recipe_sha256: 64 lowercase hex characters
  acoustic_visual_recipe_sha256: 64 lowercase hex characters
folds[]:
  fold_id: unique string
  train: recording ID list
  test: recording ID list
  unused: recording ID list
recordings[]:
  recording_id: exact catalog ID
  sample_count: positive integer, full native length
  word_onset_samples: sorted finite sample positions in [0, sample_count)
  neural_sha256: declared full source payload digest
  alignment_sha256: declared full alignment payload digest
  transcript_sha256: declared full target transcript digest
  acoustic_visual_probabilities: operator-owned finite [0,1] probabilities,
                               one per fixed-grid bin in order
```

`submission.json` has exactly `task_id`, `query_sha256`, `predictions`.
Each prediction has exactly `recording_id`, `fold_id`, `neural`; `neural` is the
ordered probability array for the full query grid. `query_sha256` is SHA-256 of
the query object's canonical JSON (sorted keys, compact separators, UTF-8;
use `evaluator.digest(evaluator.public_query(reference))`). It contains no
private-reference digest. Scores retain separate exact reference/submission
digests to let the operator audit which targets and comparator were used.

From the repository root:

```sh
python3 benchmarks/neural/NEURAL-015/implementations/fresh-output-v1/evaluator.py validate reference.json --output validation.json
python3 benchmarks/neural/NEURAL-015/implementations/fresh-output-v1/evaluator.py query reference.json --output query.json
python3 benchmarks/neural/NEURAL-015/implementations/fresh-output-v1/evaluator.py score reference.json --submission submission.json --output score.json
python3 -m unittest discover -s benchmarks/neural/NEURAL-015/implementations/initial-evaluator-v1/tests -v
```

The importable API is `validate_reference`, `public_query`, `evaluate`,
`align_onsets`, `onset_labels`, `average_precision`, `metrics`, and `digest`.
The test module's `fixture()` constructs a complete 26-ID engineering example
without authentic payloads. Its all-equal comparator and perfect generated
labels are test oracles, not a baseline result.

## Source-informed alignment helper

`align` accepts exactly `movie_times` (all private word starts, seconds),
`triggers` (list of `movie_time_seconds`, `neural_sample_index` pairs), and
`max_clock_residual_samples` (explicit nonnegative bound). It requires at least
two strictly increasing trigger clocks. Within the inclusive trigger span, the
nearest trigger is selected; equal distances select the earlier trigger.
The returned integer is Python `round(index + (time-trigger_time)*2048)`, with
ties-to-even. Every adjacent trigger interval must satisfy the declared residual
bound against 2048 Hz. No onset outside trigger coverage is silently dropped or
extrapolated; such input fails. Sorted targets and aligned monotonicity are
required. A compliant residual does not detect every dropped trigger or prove
correct movie/recording correspondence.

The paper permits pause/resume and event bursts. Thus raw recording-wide trigger
rows can repeat movie times or jump in neural time. This helper expects one
operator-reviewed **unpaused clock segment**. Invoke it separately on validated
segments, preserve recording-global sample indices, and reconcile complete word
coverage across all segments before scoring. Never increase the residual bound
merely to make a pause pass. Segment selection, ambiguous repeated movie spans,
and native trigger/event interpretation remain held; the helper cannot infer them.

```sh
python3 benchmarks/neural/NEURAL-015/implementations/fresh-output-v1/evaluator.py align alignment-input.json --output aligned.json
```

This stricter helper differs from source behavior that breaks after the last
trigger. It preserves the sample mapping inside validated coverage without
copying source code. Its output always says `native_alignment_validated: false`.
The helper neither reads native timing CSVs nor resolves their `type`/trigger
selection semantics; a reviewed normalized operator export remains necessary.

## Requirements and remaining holds

| Registered requirement | Implemented construction behavior | Remaining gap |
|---|---|---|
| Fixed grid, private timing targets | Deterministic complete grids and allowlist exporter | Neural payload isolation and authentic private packets |
| Ten people, 26 presentations, 21 movies | Immutable catalog and exact coverage | Actual source lengths, electrode selection and payload hashes |
| Outer person and whole movies, temporal guards | Joint person/movie folds and declared causal support guards | Training/adaptation execution audit and protocol admission |
| Participant-macro AUPRC and incremental log loss | Tie-aware AP, pooled per-person bins, paired trusted-control loss | Independent authentic reference and scientific criteria |
| Whole movie, balance, motion/loudness, latency controls | Fold check, weighted balance diagnostic, operator comparator, paired shift | Continuous media features, balance interpretation and competent baselines |
| Trigger interpolation and tolerance | Strict nearest-anchor helper and explicit inclusive tolerance | Native alignment accuracy, calibration, missing triggers and approved tolerance |
| Negative tests and independent checks | Generated metric, identity, leakage, clock and CLI controls | Authentic independent replication |
| Rights and source freeze | Primary-paper/version/Git pins; no third-party payload bundled | Unversioned payload SHA-256s, author code license and movie redistribution |

The [project page](https://braintreebank.dev/) states a dataset CC BY 4.0 license.
This does not resolve separate source-code licensing or third-party media
rights. No archive, neural data, transcript or movie was acquired for this work.
No model fitting, native scientific campaign, dependency installation, or
scientific admission occurred. Clinical electrode placement, stimulus overlap
and ten participants continue to limit anatomical and population claims.

The maintained CLI requires a fresh output file and refuses existing inputs or reports, including linked aliases. The original numerical evaluator remains unchanged and is imported with exact source pins.
