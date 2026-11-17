# Complete-field fUS representation component

This source implements the prospective registered FUS-DIRECTION response-map
transformation. It adds a missing preparation component to the existing grouped
scorer; it is not a new benchmark or a completed native input bridge. No
authentic signal, MAT file, image, participant model or reference fit was read
or run for this delivery. The complete declared population remains 49 records,
48 positive records, two macaques and 20,622 declared source trials. Counts are
source metadata, not observed authentic arrays.

## Concrete interface

Import `prepare_fold` from `fullfield.py`, with the exact included `scorer.py`
and `roster.py` available alongside it. These two dependencies are byte-identical
copies of the already accepted V2 scorer components. Call:

```python
receipt = prepare_fold(
    frozen_adjudicated_intake, load_record, stage_map,
    held_record_id=selected_positive_record,
    fold_key=operator_generated_opaque_fold_key,
)
```

`load_record(record_id)` is an evaluator-owned source callback. It returns the
complete normalized record described below, never a guessed original MAT
schema. `stage_map(payload)` retains output privately and must not publish or
commit any fold until `prepare_fold` returns successfully. If validation or a
callback fails after maps have been emitted, those are incomplete staged
artifacts, not an admitted fold. This component does not implement filesystem
transactions, resource enforcement, source-byte authentication or a protected
process. An authentic owner still has to bind all of them.

The accepted scorer first validates all 49 intake rows and all 20,622 source
slots, including independently adjudicated exclusions and the explicit zero
record. The component then calls the source callback for each of the other 47
positive records once, in frozen intake order. It computes the finite absolute
delta maximum over every eligible training map, including training calibration
and query trials. Only after that strictly positive finite scale is fixed does
it call the held-record callback. Zero or all-invalid training maps refuse the
entire fold before held-record pixels can be read. This call order prevents
this component from deriving scale from held pixels; it is not proof that a
malicious callback or an external producer has no other access.

One call prepares one of the 48 prescribed outer folds. A complete study must
prepare all 48 independently, preserve fresh construction/inference contexts,
and keep each fold's private artifacts separate. No loop here grants access to
previous held-record results. Eight earliest eligible source-order trials, one
per direction, are calibration; every other eligible trial is a query. The
all-eligible arithmetic gives 20,238 queries across the full outer-fold roster,
but authentic eligibility remains unestablished.

## Required normalized input

Each positive record is an exact dictionary with `schema` equal to
`fus_normalized_fullfield_record_v1`, `record_id`, `native_hz` (matching the
frozen intake's 1 or 2), `source_float` (`binary32` or `binary64`), native
`shape=[y,x]`, `spatial_pitch=[y_pitch,x_pitch]`, `spatial_pitch_unit`,
`acquisition_census_sha256`, and `trials`.

`trials` has exactly every frozen source slot in source order. Each dictionary
has only `source_trial_id`, `source_order` and `frames`. An independently
adjudicated excluded trial has `frames=None` and remains in the census; this
component cannot introduce a new exclusion. Every eligible trial has its
complete source acquisition catalogue. Each frame contains exactly `frame_id`,
`source_order` (zero-based contiguous within that catalogue), `start`, `end`,
`complete` (a strict boolean), and `pixels` (a flat y-major list of exactly
`y*x` native pixels). Durations must be positive. Complete and incomplete
frames remain in the catalogue; no catalogue truncation or selective pair
submission is authorized. The code checks the declared shape of every frame
and the selected operands' floating values. It does not inspect unused pixel
values to choose a favorable frame.

The independent acquisition-census digest is required syntactically. A digest
cannot prove that a producer supplied every real frame, resolved a Run99
duplicate, reconstructed a clock, preserved native pitch/orientation or used
an allowed source. Those authentic provenance responsibilities remain held.
The normalized schema is prospective software input, not a claim about
uninspected original field names or the original arithmetic dtype.

Finite pixels must be exactly representable in the declared source format;
silent dtype casts are refused. Explicit `"nan"`, `"+inf"` and `"-inf"` tokens
preserve nonfinite native operands without nonstandard JSON numeric literals.
No arbitrary per-pixel missingness rule is introduced. A future native bridge
must preserve and authenticate source operands and declare the actual format.
Unsupported arithmetic formats refuse; they cannot trigger record exclusion.

## Scientific operations

The baseline is the unique latest complete acquisition ending strictly before
cue. The response is the unique latest complete acquisition whose entire
interval is inside the memory epoch and ends no later than go. A tie for the
latest end is ambiguous and refuses. Earlier, partial, crossing-boundary or
post-go frames cannot substitute. Selected start/end values must also match
the frozen scorer intake exactly; an inconsistent intake requires independent
re-adjudication, not a silent correction here. No sample duration is inferred
from 1/2 Hz, no downsampling occurs, and no across-trial median is used.

For each native pixel the operation is `(memory-baseline)/baseline`. Both the
subtraction and division are rounded separately in the declared IEEE binary32
or binary64 format with round-to-nearest/ties-even and gradual underflow. The
stdlib implementation uses exact rational intermediates to avoid double
rounding; it does not algebraically reassociate the source expression. For
example, a genuine overflow in subtraction remains invalid even if an
alternative ratio-minus-one expression would be finite. Nonfinite operands,
baseline at/below zero, or nonfinite results produce the explicit invalid mask.
Signed zero has no effect on these positive-denominator response maps.

For each outer fold, `s` is the maximum absolute finite delta across all other
47 positive records. Valid pixels are encoded with the literal registered
formula `floor(127.5*(clip(delta/s,-1,1)+1)+0.5)`. The quantizer is evaluated
exactly on the already rounded scalar values, so half steps round upward
without an intermediate binary tie flip. A value exactly at `+s` or `-s`
is not called saturated; only values outside that interval are clipped and
counted. Unclipped reconstruction error is at most `s/255` in mathematical
scalar units. Each gray pixel is repeated into three uint8 channels; invalid
pixels are exactly magenta `(255,0,255)`.

No native spatial pixel is removed, cropped, averaged, resized or chosen by
label. Output `rgb` is immutable bytes in y-major RGB order with exact shape,
pitch/unit, native rate, source float format, scale, invalid count and saturated
count. This is a raw RGB artifact interface, not an image codec or a vision
API. Calibration payloads contain the direction; query payloads do not contain
direction, source record/trial/frame IDs, source order, acquisition times,
behavior fields or source filenames. Opaque IDs are syntax-checked but their
random assignment and absence of lookup channels require external review.

The output stream is evaluator-private. It is not a participant context:
participant delivery still requires exactly the same eight calibration maps
plus one query, fresh state per query, identical bytes across access arms, and
separately qualified full-resolution image delivery. No function here supplies
held-session maps to prompt/program construction.

## Evidence and remaining work

Eleven generated methods exercise the complete logical census, all 47 training
records, held-pixel saturation without scale leakage, earliest calibration,
query redaction, zero-scale refusal, late staged-output failure, full grid and
trial joins, incomplete/boundary/tied acquisitions, independently adjudicated
missingness, binary32/binary64 rounding and a closed-form quantization bound.
These controls establish software behavior on invented arrays, not authentic
method competence or source validity. Their measured peak is not an authentic
resource bound. The accepted grouped scorer's numerical tests were not rerun
because its bodies are unchanged.

The retained writer inquiry did not find `createDoppler`/`parsefUSBehavior` or
the five exact Run99 invocation lists. Motion/registration helpers do not
establish acquisition timestamp meaning, memory-end events, frame duration,
complete trial lineage, crop/pitch/orientation or export precision. No new
network inquiry or signal access resolves those deficits in this delivery.
Whole-session source registration also remains an offline exposure limitation.
The concrete next source input is the genuine acquisition/export producer and
complete original acquisition/trial lineage, not another inferred MAT loader.

Native source authentication, complete biological reconciliation, rights,
native-clock/dtype/grid parity, resource qualification, competent full-field
references, masked-map controls, same-nine-map participant delivery, protected
runtime and contamination analysis remain unqualified. All qualification flags
are false; the registered task, contracts and counts stay unchanged.


## Portable distribution

This directory is self-contained standard-library source. The three scientific
runtime bodies `fullfield.py`, `scorer.py`, and `roster.py`, plus the eleven-method
`test_fullfield.py`, are byte-identical to the reviewed source. The five
independent scientific witness functions and their two helpers are unchanged;
only their import and test-discovery harness has been relocated. The old private
registry-composition check, private source selection and receipt writer are not
published. `SCORER_SCHEMA.md` preserves the complete existing scoring interface.

Run the four **packaging-only** checks from any working directory with
`python3 -I -S -B /path/to/this/directory/test_delivery.py`. They authenticate the
complete source manifest, load the sixteen retained scientific tests without
running them, and exercise relocated dependency admission and tamper refusal.
These checks do not construct an invented full cohort or recompute the accepted
numerical tests. CI selects only these new packaging checks for this projection.

To run the retained numerical suite separately, first verify `SOURCE.json` and
all its members against the pinned manifest identity in the accompanying CI
fragment or a trusted release. Add this directory to the isolated interpreter's
module search path and use unittest on `test_fullfield` and `test_independent`.
This is an explicit generated-test action, not an authentic benchmark run.
A caller using the `prepare_fold` or `scorer.evaluate` API must likewise admit
the exact source graph before imports and provide its own reviewed authentic
inputs, staging/commit boundary and resource limits. No authentic fixture,
answer, current native source map or production runtime is supplied here.

The retained numerical evidence is eleven author methods and six independent
checks from the source review; five of the latter are scientific witnesses and
one is private registry integration. This public projection neither replays nor
converts that evidence into a new scientific result. Native clock/producer,
Run99 lineage, geometry/dtype, references, all48 authentic folds and participant
image delivery remain unresolved.
