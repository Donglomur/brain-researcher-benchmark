# Complete-recording seizure-event evaluation

This component implements a **conditional evaluator for normalized predictions**
under a named prospective protocol. It requires all 686 recordings in the pinned
CHB-MIT 1.0.0 `RECORDS` manifest, grouped into 23 biological people. `chb21` and
`chb01` belong to the same person and are held out together. It supplies source
admission checks, complete sample-score coverage checks, event scoring, sample
diagnostics and constant controls. It adds no benchmark ID.

The [canonical task](../../task.json) remains unchanged. Actual EDF payloads,
normalization, clocks, montage interpretation, model fitting, protected execution
and scientific qualification remain unverified. Metadata commitments and generated
tests do not establish any of those properties.

## Frozen prospective protocol

[recommended_policy.json](recommended_policy.json) defines the exact supported
complete-cohort profile. A caller supplies its previously frozen canonical JSON
SHA-256; changed thresholds or tolerances require a separately reviewed profile.

| Choice | Definition and provenance |
| --- | --- |
| Observation support | Every pinned recording, including seizure-free background; score each file independently and sum only its observed duration. Never fill inter-file gaps. |
| Biological split | 23 leave-one-person-out folds; each fold trains on the other 22 people and evaluates every recording of the held-out person. |
| Scores | Complete probabilities on an explicit 10 Hz output grid, encoded as adjacent half-open run intervals; positive if probability is at least 0.5. |
| Context | Causal through the prediction-bin endpoint; no later EEG or answer-bearing metadata. This declaration is not physical enforcement. |
| Event scorer | Exact MIT-licensed `timescoring` source at commit `426f8d2b77974641dc9db71884e0812b249ba93b`, executed from verified source bytes rather than bytecode caches. |
| Source parameters | Start/end tolerances 30/60 seconds; merge gaps strictly less than 90 seconds; split events longer than 300 seconds; minimum overlap 0 with the source's strict `+1e-6` comparison. Both reference and predicted events undergo merge/split. |
| Primary endpoint | Sum processed event counts within each biological person, then take the mean of 23 person-level event F1 scores. If any person's F1 is undefined, the primary result is null with the affected identities retained. |

The source scorer fixes its event precision at 10 Hz. This profile admits only
integer output ticks, with native sample count/rate exactly consistent with that
duration. It neither resamples EEG nor invents a native-to-output score mapping.
The fixed probability threshold, causal context, complete LOPO split and
record-boundary resets are **prospective benchmark choices**, not claimed optimal
settings or published clinical recommendations.

Freeze the entire recipe before outer evaluation. Fit preprocessing, calibration
and model parameters only on the outer-training people. Any tuning requires inner
person-held-out selection within those people. Do not fit on the held-out person's
unlabeled inputs unless a separately reviewed access condition permits it. The
current evaluator checks declarations and predictions, not training execution.

## What the metrics mean

This is **tolerant retrospective event-presence coverage**, not onset timeliness.
Processed events after merge/split are not original clinical seizure counts.
The output retains both raw and processed counts.

The source algorithm is not one-to-one matching: a reference event is detected
when the union of hypothesis-positive samples overlaps its extended window enough;
a predicted event is a false alarm only if it does not overlap any detected
reference window. Consequently one long prediction can detect several references.
Event F1 is `2 TP / (reference_count + TP + FP)`. Sensitivity is undefined with no
reference events, precision with no TP/FP, and F1 with no references and no FP.
Undefined values become JSON null, never a silently omitted person.

Mandatory sensitivity and false alarms per 24 observed hours are reported per
person, with explicitly labeled person-macro and pooled diagnostics. The
false-alarm denominator includes **all observed time**, including seizure and
tolerance windows; it is not only non-seizure background. Record gaps contribute
no exposure and cannot merge events across files under this profile.

Unmerged, unextended sample-level sensitivity, precision, F1 and predicted-positive
time fraction accompany the event metrics. Full-support all-negative and
all-positive controls are also scored. Constant probabilities are valid weak
detectors, not malformed submissions. These controls do not replace a competent
EEG-derived reference or timing/montage-only control. Sample metrics and occupancy
do not establish event-onset latency.

### Original-event alarm diagnostics

Each candidate recording result additionally contains `raw_event_alarm_diagnostics`
(`raw-event-alarm-diagnostics-v1`, `tick_rate_hz: 10`). Its `events` list follows the
original reference intervals, before tolerant extension, merging or splitting.
These diagnostics do not change the primary F1, any existing count, or sample
occupancy. They are not additional candidate inputs or candidate feedback.

For an original half-open event `[a, b)`, each row contains:

| Field | Meaning |
| --- | --- |
| `reference_event_index` | Zero-based position in this recording's original reference list. |
| `reference_duration_ticks` | `b - a` on the existing 10 Hz grid. |
| `onset_alarm_state` | `negative`, `new_alarm` for an alarm starting at `a > 0`, or `continuing_alarm` for an alarm already positive before `a`. At `a == 0`, the separate states `positive_at_record_start` and `negative_at_record_start` preserve the unobserved antecedent. |
| `first_new_alarm_offset_ticks` | First within-record alarm start `s` satisfying `a <= s < b` and `s > 0`, minus `a`; null if none. This can be present even when the onset state is `continuing_alarm`. |
| `positive_overlap_ticks` | Number of positive ticks inside the original `[a, b)` event, without tolerance. |
| `no_raw_event_overlap` | True exactly when that overlap is zero; this is not the tolerant scorer's false-negative count. |

Touching positive intervals form one continuous alarm for these diagnostics, so
partitioning a positive run cannot manufacture new rising edges. Reference events
remain separate: an alarm bridging two original seizures can start within the
first and be continuing at the second. An alarm ending exactly at `a` or starting
exactly at `b` has no overlap with that event. Recordings remain independent; no
state or time is carried across a recording boundary. An empty reference list
produces an empty diagnostic list; existing false alarms and occupancy still
account for predictions in background recordings.

Offsets describe prediction-grid alignment, **not measured online decision
latency**. In particular, an offset of zero does not establish a zero-delay
decision: permitted causal observations extend through the prediction-bin
endpoint, and the evaluator does not verify when a prediction was produced.
These fields neither establish causal execution nor attribute tolerant credit
one-to-one to original seizures. Actual timing, early/late-only-credit attribution
and clinical performance remain unqualified. The new reference-linked fields stay
inside the owner-only result, including when they reveal original-event duration.

## Input and output interfaces

[core.py](core.py) contains the exact schemas and Python interface. Unknown fields,
duplicate recording IDs, missing recordings, wrong patient aliases, incorrect
fold membership, non-finite probabilities, score gaps/overlaps and contradictory
threshold intervals are refused.

- **Operator admission** (`neural009_admission_v1`): the source-index identity,
  complete LOPO fold list, normalization/clock/rights review commitments and all
  686 normalized recording rows. Each row supplies the publisher EDF hash,
  header and annotation commitments, native sample count/rate, observed ticks,
  montage roles and selected EEG channel indices, and private reference intervals.
  Explicit zero-event annotation coverage is distinct from absent annotation.
  Duplicate bipolar channel labels are allowed; selected annotation/non-EEG roles
  are refused. The declarations are not verified against physical EDF bytes here.
- **Public support** (`neural009_public_support_v1`): `public_support(admission)`
  projects only source/fold identity, recording IDs, biological people, durations,
  native count/rate and selected predictor channel metadata. It contains no
  reference events, annotation status or annotation hashes. A label-only change
  cannot change the candidate's support commitment.
- **Candidate** (`neural009_candidate_v1`): task/source-index identity, the public
  support hash, frozen policy hash, recipe hash, and all 686 prediction rows. Each
  row has its exact recording/person/fold identity, `score_runs` as
  `[start_tick, end_tick, probability]` triples covering every observed tick, and
  `predicted_intervals` exactly equal to thresholded runs before source merge/split.
- **Limits**: positive integer `max_record_ticks`, `max_total_ticks` and
  `max_prediction_segments`. Exceeding a limit refuses the whole evaluation;
  no population is truncated. These are explicit operator resource declarations,
  not measured native execution guarantees.
- **Result** (`neural009_result_v1`): complete per-record and per-person counts,
  primary F1, mandatory and sample diagnostics, constant controls, input identities
  and explicit false scientific-verification flags. Candidate `record_results`
  also include the original-event diagnostics above; constant-control summaries
  retain their existing aggregate count/sample interfaces. Results and the full admission
  hash are operator-only artifacts; never return them as candidate feedback.

Reference intervals and score runs use half-open integer intervals on the 10 Hz
grid. Reference intervals must be ordered, non-overlapping and inside observed
support. `evaluate_record` is a low-level source-parity helper; it admits explicit
aligned source parameters and relies on its caller for memory bounds.
`evaluate` and the CLI enforce the fixed complete-cohort policy and declared limits.

## Operator commands

Python 3.11 and NumPy are required for scoring; no dependency is installed by the
component. The isolated `-I` commands below require NumPy in the selected
interpreter's environment (for example, an existing virtual environment), not
only its user-site directory. Local generated tests also record the ordinary
interpreter route when NumPy is available only in the user site; that does not
qualify an isolated deployment environment. Obtain `SOURCE_MANIFEST_SHA256` from the reviewed release's current
descriptor, not from an untrusted replacement tree. `POLICY_SHA256` is the
canonical policy digest reported by the verified source command.

```sh
python3 -I -B cli.py verify-source \
  --expected-manifest-sha256 "$SOURCE_MANIFEST_SHA256"

python3 -I -B cli.py public-support \
  --expected-manifest-sha256 "$SOURCE_MANIFEST_SHA256" \
  --admission operator-admission.json --limits limits.json \
  --output public-support.json \
  --max-input-bytes "$INPUT_BYTE_BUDGET" --max-output-bytes "$OUTPUT_BYTE_BUDGET"

python3 -I -B cli.py evaluate \
  --expected-manifest-sha256 "$SOURCE_MANIFEST_SHA256" \
  --policy recommended_policy.json --expected-policy-sha256 "$POLICY_SHA256" \
  --support public-support.json --candidate candidate.json \
  --admission operator-admission.json --limits limits.json \
  --output private-result.json \
  --max-input-bytes "$INPUT_BYTE_BUDGET" --max-output-bytes "$OUTPUT_BYTE_BUDGET"
```

Run these from this package. Input byte caps apply separately to each JSON input;
the output cap applies to serialized result bytes. The CLI opens regular files
without following final symlinks and refuses FIFOs rather than waiting for writers.
Public candidate, policy, support and budget checks precede reference-table reads.
Outputs must be fresh paths and are created with owner-only mode. Require successful
exit and the complete result: failed I/O may leave a partial newly created output.
This is not hostile concurrent-filesystem protection or a protected model runner.

The current source manifest verifies the package bodies against the independently
supplied manifest digest. The original scorer and annotation files are retained
byte-exact with their [MIT license](vendor/timescoring/LICENSE). The
[source provenance](source_provenance.json) records original URLs and identities.
The recording identity table derives from the
[CHB-MIT database](https://physionet.org/content/chbmit/1.0.0/),
[RECORDS](https://physionet.org/files/chbmit/1.0.0/RECORDS), and
[publisher checksums](https://physionet.org/files/chbmit/1.0.0/SHA256SUMS.txt).
Attribute the CHB-MIT contributors and PhysioNet; the source database's
[ODC-By 1.0 terms](https://physionet.org/content/chbmit/view-license/1.0.0/)
remain applicable. No signal payloads are redistributed by this component.

## Validation and remaining gates

Generated controls exercise full 686-record/23-person support, independently
calculated event counts, alias grouping, gaps, sample occupancy, null behavior,
source corruption and public/private admission ordering. They establish software
behavior on those controls, not authentic-data agreement.

The existing `tests/construction/test_seizure_events.py` suite also checks
original-event alarm alignment using hand-calculated boundaries, continuing and
bridging alarms, touching runs and record-start uncertainty. Run that suite from
the repository root with the existing Python 3.11/NumPy environment. Its generated
complete-cohort regression preserves the original primary/count/sample outputs
and checks that new diagnostics do not enter public observation support.

Before scientific qualification, authenticate actual EEG/header/annotation bodies,
complete clocks and montage roles, causal normalization and source rights; execute
and independently verify a competent EEG-derived detector and timing/montage-only
control under complete held-out-person monitoring; qualify protected execution and
resource feasibility. Patient-paired uncertainty needs a frozen resampling and
reference-comparison protocol with an explicit interpretation of overlapping LOPO
training sets. It remains deferred; constant-control comparisons do not close it.
Public source data remain development data. No clinical validation, onset-detection
claim, authentic reproduction or whole-task qualification is supplied.
