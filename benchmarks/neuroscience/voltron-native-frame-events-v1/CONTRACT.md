# Voltron V3 native-frame event-scoring core

This implements the mathematical and complete-coverage scoring component for
the existing `NEURAL-DISC-20261114-VOLTRON-SPIKES` task, under the explicitly
specified `voltron-six-subject-native-frame-events/v1` profile. It preserves the
old seven-animal integer-grid scorer. It creates no new benchmark ID and does
not establish an authentic packet, qualified reference, candidate result or
submission-ready task.

The accepted V3 proposal specifies all 34 deposited movies, 12 cells and six
subjects. The endpoint predicts independently established electrical events
from prepared optical traces. This is a prospective spike task; it is not a
reproduction of the paper's five-cell smoothed trace-RMS comparison. Optical
ROI/target identity, deposited motion state, extraction, native timestamp dtype
and physical synchronization, electrical spike detection and comparator
producers remain separate unresolved work.

## Exact event matching

Predictions are sorted unique optical frame indices. Each index selects the
stored native exposure-midpoint value, already expressed in electrical seconds.
There is at most one prediction per frame; there is no subframe localization or
same-frame multiplicity. No nominal 400/1000-Hz clock, repeated movie offset,
resampling, motion correction, demo crop or stimulation conditioning is applied.

`exact_time` accepts a literal Python integer, finite Python float, or explicit
integer ratio. A float is interpreted using `as_integer_ratio()`: its exact
represented binary value, not its shortest decimal string. A qualified upstream
adapter must preserve the actual dtype's value. For a type that cannot be
converted to Python float without loss, supply its exact integer ratio. There
is no NumPy import, generic float coercion or assumed float64 input. These exact
arithmetic rules do not establish zero physical timestamp uncertainty.

Matching compares rational values against inclusive `1/200` second. The
earliest compatible prediction and reference are paired. A point earlier than
the opposite earliest point minus the tolerance can be discarded because it
cannot match any later point. When both earliest points are compatible, a
maximum matching can be exchanged to contain that pair: if they were paired
elsewhere, swapping the two edges leaves the other edge compatible by ordering.
Induction proves maximum cardinality. Latency follows this deterministic
earliest-compatible assignment; it does not minimize total or nearest latency.

Frame cores partition every movie's stored frame indices exactly. Predictions
are reassembled into complete movies before matching, so core boundaries do not
block a valid pair. Matching is independent in each connected half-open valid
interval. Adjacent intervals are coalesced; a positive invalid gap is never
crossed, even when events on its opposite sides are less than 5 ms apart.
Reference events outside declared valid support are a reference error.
Predictions outside that support remain explicit excluded counts, not true or
false events. No reference event is silently removed to improve a score.

## Scores, coverage and representation ceiling

Movie TP/FP/FN counts are summed over **all** movies of a cell before cell F1:
`2TP/(2TP+FP+FN)`. Empty/empty is undefined, never one. False predictions with no
reference events give F1 zero, precision zero, undefined recall and a real
false-events-per-valid-minute burden. Zero valid duration makes that burden
undefined. Matched signed mean/median and absolute mean latency are retained.

The primary output is **six subject-specific, equally weighted cell-F1
values**. It is not a pooled event score or a cross-subject headline. An
undefined cell keeps its subject's full equal-cell value undefined. A separately
named observed-only mean is secondary and does not replace it. Candidate-minus-
comparator contrasts retain negative and undefined values. No significance,
improvement threshold or global scalar is introduced.

Every movie/cell remains in the result, including optical-extraction failures,
partial validity and unscorable support. Exact valid and total durations,
coverage fractions, failed/partial/unscorable counts, frame counts and excluded
predictions remain available through movie, cell and subject rows. Nominal
camera-rate strata are labeled metadata strata; they neither define nor claim
to measure the native cadence.

After all role predictions are captured, the evaluator also matches **all
eligible native frame centers** to every reference event, separately within
connected valid intervals. With reference count `N` and maximum matches `M`,
the private output-representation ceiling reports recall `M/N` and F1
`2M/(M+N)`. Both are undefined for `N=0`. Extra eligible centers do not create
ceiling false positives because an oracle can output only the matched subset.
Neighboring centers may match distinct events within 5 ms; same-frame bin
counts are not a substitute. Only movie/cell aggregate counts and metrics are
returned, never oracle indices, pairs or event locations. This measures the
output representation, not what can be recovered from optical traces. It stays
evaluator-only and cannot guide candidate fitting or ROI/reference selection.

Counts, interval decisions, matching and intermediate duration/latency/cell
weighting arithmetic are exact. Convenience metric floats are presentation
values. Exact duration and latency ratios accompany them. A positive duration
so small that the false-event rate cannot be represented as a finite float
retains the exact rate ratio and an explicit
`overflow_exact_ratio_retained` presentation flag; its convenience value is
null. This is distinct from `undefined_no_valid_time`. No infinity is emitted,
no native time is clipped, and no empty-case convention is changed.

## Pure library interface

`grade(public, predictions, private_loader)` executes no participant code. It
validates and captures every role and final core into independent immutable
tuples before its one trusted private callback. Invalid submissions return
`invalid_submission` with zero private calls. Invalid public/reference
geometry, roster, clock ordering or fold coverage raises a typed error. Private
reader failures propagate as operational failures, not zero scores. Successful
source scoring still sets `scientific_qualified=false` and `new_benchmark_ids=0`.
This library is not a process boundary; a future protected harness must keep
assessment reference material inaccessible to participants.

The source JSON contract has these exact fields:

- Public: `schema="voltron-native-frame-public/v1"`, `task_id`, `profile`,
  `release_manifest_sha256`, `cells` (12 unique opaque IDs),
  `expected_subjects=6`, and `movies` (exactly 34 unique opaque IDs).
- Each public movie: `cell_id`, `fold_id`, `nominal_optical_rate_hz` (400 or 1000
  as a label), `start_time`, `end_time`, `frame_times`, `input_disposition`
  (`ready` or `optical_extraction_failed`), `optical_valid_intervals`, and `cores`.
  A core has `core_id`, `start_frame`, `end_frame`; complete half-open index
  ranges partition `[0,len(frame_times))`. Movie support is separately supplied
  in physical seconds; it is not inferred from frame spacing. Failed extraction
  still retains its complete validated clock/core population and empty optical
  validity.
- Predictions: `schema="voltron-native-frame-predictions/v1"`, `task_id`,
  `public_sha256`, and `roles`. Required roles are `candidate`, `optical_mad`,
  `optical_matched_filter`, `metadata_rate`. Each has `program_sha256`,
  `calibration_sha256` and the complete mapping `cores` to sorted unique literal
  integer frame indices. Boolean, floating, duplicate, wrong-core and omitted
  indices/core panels are rejected before reference access.
- Private callback result: `schema="voltron-native-frame-reference/v1"`,
  `task_id`, `public_sha256`, `census_evidence_sha256`,
  `mapping_evidence_sha256`, `cell_to_subject`, `outer_folds`, and `movies`.
  Each fold has `query_subject` and exactly all other subjects' `train_cells`.
  All movies follow their cell's subject fold. Each private movie has
  `valid_intervals` and `spikes` at actual electrical sample times. Private
  intervals must lie inside public optical validity.

Public/private JSON time values are integer/finite-float scalars or
`[numerator, positive_denominator]`. Scalar ratios are normalized internally.
The low-level matcher also accepts Python `Fraction` values; JSON public
identity requires explicit ratio lists instead. Identity uses sorted compact
finite JSON. Source hashes identify supplied artifacts, not proof of legitimate
calibration, clock authenticity or biological mapping.

`match_events(predictions, truth)` is the standalone validated mathematical
helper. It returns `(TP, FP, FN, signed_latency_Fraction_tuple)` and accepts
strictly sorted unique scalar/rational time vectors. Its private event inputs
and latency tuple belong to trusted evaluator code, not participant tooling.

Format refusal ceilings are 10 million total frames, one million events per
role/reference, 200,000 cores/validity spans, 4,096-bit integer-ratio operands
and time magnitudes at most `2**63` seconds. These are format limits, not a
measured full-cohort memory/time envelope or permission to truncate. Arbitrary
large-denominator rational arithmetic can be costly; the future adapter must
qualify actual native dtypes and budget the complete prepared task. Source
controls do not authorize authentic decoding or execution.

## Generated verification and remaining work

Run `python3 -I -S -B test_event_score.py`. The invented fixture covers all
34 movies, 12 cells, six subjects, four roles and complete frame cores. Author
controls compare 1,024 point-set pairs to an independent dynamic-programming
cardinality oracle. The separate peer controls exhaust 4,096 small bipartite
matching instances and independently check exact boundaries, ties/greedy traps,
gaps, complete freezing, aggregation, undefined behavior and overflow handling.
Neither suite reads released signals, electrical references or held answers.

Before authentic use, qualify all source clocks, optical target/motion/trace
preparation, electrical reference production, the three training-only comparator
producers, six subject holds and the actual protected runtime. Public historical
exposure, physical clock uncertainty and unresolved within-exposure multiplicity
remain limitations. Full input/reference annotation has not been selected here.
