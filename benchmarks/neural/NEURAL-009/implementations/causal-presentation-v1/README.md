# Causal EEG presentation and complete probability binding

This inactive operator component connects the accepted calibrated classic-EDF
reader to a typed SVG presentation and the existing complete-cohort probability
scorer. It supplies no detector, model run, authentic EEG result, protected host,
new endpoint or activated participant mode. SVG is a vector representation whose
coordinates can be parsed; it is not raster presentation or evidence of native
visual understanding. The canonical task and its access-condition statuses remain
unchanged.

The existing `seizure-events-v1/core.py` accepts all 686 recordings and 23
biological people, including the shared chb01/chb21 person. Its 10 Hz grid,
probability threshold, source event matching, tolerance, merging and macro rules
are reused unchanged. The earlier `edf-causal-window-v1` reader must be installed
as its separately reviewed prerequisite; this package does not copy or change
that reader. Current published source context and exact pins are in SOURCE.json.

## Operator construction

`Cohort` takes the existing **operator-private** support projection, frozen policy,
explicit rendering protocol, their externally frozen canonical SHA256 identities,
the recipe commitment, existing scorer limits, and an operator-secret key of at
least 32 bytes. The current core function called `public_support` contains source
filenames/persons/source-index hashes and must not be delivered to a participant.
The new component detaches caller operands before use. The key must be generated,
protected and reused only according to an independently specified host protocol;
the generated test key is not a deployment key.

The protocol's exact fields are `schema=neural009_typed_svg_protocol_v1`,
`lookback_ticks`, `width_px`, `channel_height_px`, `max_svg_bytes`,
`max_total_svg_bytes_per_record`, `max_actions_per_record`, `max_views_per_tick`,
`max_window_samples`, `max_window_values`, and `scales_uv`. Every field is supplied
by the operator; no clinical scale, lookback, channel subset or action budget is
guessed. `scales_uv` contains one ordered `{index,minimum,maximum}` list for every
original recording, exactly covering its independently admitted predictor
channels. Duplicate bipolar labels retain separate source indices and bands.
The scale map and support are private. A matching digest binds supplied metadata;
it does not authenticate channel roles, clinical clocks, complete annotations or
chronology of freezing.

`case_ids()` returns HMAC IDs in opaque-ID order, rather than source-filename order.
The operator calls `start_edf(case_id, private_path, admitted_row,
max_edf_bytes=...)`. This binds the original filename/person/publisher hash, native
support and ordered predictor channels before constructing the unchanged reader.
That reader authenticates the complete file/header and selected calibration. The
operator must already have authenticated the complete source admission and its
independent clock, channel-role/duplicate handling and source-rights decisions.
The private `_start` factory seam is an implementation/test seam, not a participant
extension or a substitute for this source binding.

Only `start_edf`'s sanitized reply and `dispatch` replies cross the participant
boundary. No Python object, factory, file path, source hash, annotation, target,
raw sample array, complete source support or final scorer object is a participant
capability. A separate host must enforce that boundary. Python attribute naming
and HMAC identifiers do not create filesystem/network isolation, prevent source
fingerprinting, or control model/tool access and cross-case memory.
The host must serialize owner calls and avoid concurrent input mutation; this
synchronous component does not provide a multithreaded transport. The external
decoder must bound request bytes before creating Python objects. `dispatch`
itself accepts only a constant number of immutable primitive fields, without
serializing or traversing nested candidate values.

## Typed interaction and exact clock

At the first active endpoint, tick 1 is 0.1 seconds and the answer covers output
bin `[0,1)`. A view request has exactly `action="view"`, `case_id`, `end_tick` and
`lookback_ticks`. It must lie within the frozen surrounding causal history and
cannot exceed the active endpoint. Native sample `j` has time `j/Fs`; the first
sample is the ceiling of the requested lower time boundary, and the last included
sample is the floor of its upper boundary, bounded by actual recording extent.
Thus a sample exactly at 0.1 seconds is available for tick 1. The accepted reader
checks availability again. There is no filtering, resampling, lag search,
acquisition-gap filling, or cross-record window.

The SVG plots every selected sample and channel with the frozen microvolt ranges.
Every source label is XML-escaped. It contains no script, external resource, raw
array field or source identifier. Samples outside the declared range cause a
retained presentation failure rather than silent clipping or autoscaling. Render
byte, cumulative byte, view-count, native-value and action bounds are explicit.
These bounds are engineering guards, not measurements of full-source capacity or
OS memory isolation. SVG display needs a separately selected host/rendering path.

An answer has exactly `action="answer"`, `case_id`, integer `tick`, and a finite
numeric `probability` in `[0,1]`. Boolean values are refused. Only the active tick
can be answered; successful answers advance irreversibly before later EEG becomes
available. Repeating or revising an earlier answer cannot alter its stored value.
Skipping views is allowed, preserving valid weak constant controls. There is no
score feedback. Logical 10 Hz availability does not assert physical real-time
operation, fast inference or clinically timely detection.

## Failure-inclusive output and scoring

The operator calls `finish()` to obtain a private ledger containing all 686
recordings, including not-started, active, failed and complete cases. It returns
no candidate while any record is incomplete. Source open/authentication errors,
unsupported EDF+C/D, invalid presentation, exhaustion and cleanup failures remain
in that ledger. Replies use fixed failure codes and never raw exception text.
The source reader's classic-EDF restriction is not silently expanded because the
older geometry admission helper permits EDF+C. No record may be dropped to turn
such a failure into a complete cohort.

`abort_active()` is an owner-only timeout/cancellation hook with fixed failure
codes. It closes the current reader and keeps the failed case. A failed or
interrupted close retains ownership, records its count, prevents further answers
and blocks opening another case until cleanup succeeds. A later abort retries
closure without erasing the original failure or creating a successful case.
Uncatchable termination and host failure still require external containment.

Only complete monitoring yields the existing `neural009_candidate_v1` object.
Adjacent equal probabilities are losslessly compressed into contiguous runs;
the unchanged scorer derives threshold intervals and prevalidates full identity,
fold, segment and tick support. The candidate and ledger remain private. A
separate trusted operator supplies the original normalized reference admission to
the unchanged `core.evaluate`; this interface does not deliver a new annotation
endpoint or choose a favorable event statistic. Original source authentication,
full execution, competent EEG/timing comparators, exposure control, paired
uncertainty and scientifically meaningful results remain unqualified.

## Verification and integration

The new generated checks exercise the real reader on tiny invented EDF bytes,
the complete 686/23 metadata support, failure/refusal boundaries, SVG escaping,
opaque ordering, irreversible answers and the unchanged event scorer. Full-roster
signals/targets in those controls are explicitly generated engineering operands;
they are not authentic CHB-MIT data or benchmark performance measurements. No old
reader/scorer test suite is replayed.

From repository root, the proposed maintained command is:

```text
python3 -B benchmarks/neural/NEURAL-009/implementations/causal-presentation-v1/tests/test_presentation.py
```

It needs the existing NumPy dependency used by the unchanged scorer. For a private
source check, `--implementations` selects the exact-pinned dependency mirror.
No dependency is installed by this component. The sole integrator must co-adopt
the earlier accepted EDF-reader files, add this new component and its focused
command to source ownership/CI, and compose applicable current source pins.
Historical evidence and canonical task/mode/science status stay unchanged.
