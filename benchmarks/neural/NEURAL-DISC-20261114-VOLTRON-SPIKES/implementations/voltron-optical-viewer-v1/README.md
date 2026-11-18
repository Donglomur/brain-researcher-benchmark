# Optical trace viewer and native-frame response collector

This component fills the missing typed-viewer and first-final response API for
`NEURAL-DISC-20261114-VOLTRON-SPIKES`. It uses the existing six-subject,
twelve-cell, 34-movie native-frame scorer unchanged. It does not supply authentic
optical traces, electrical labels, a protected participant process or an AI run.
The task remains a partially delivered prospective optical spike-event task.

`Session` accepts the complete current public scorer contract and a prepared
optical packet. It freezes all native clocks and optical sample values, then
exposes only the selected held fold's core catalog, typed views and answers.
Public geometry must assign all movies of a cell to one fold; no number of
cells per fold is invented. This necessary consistency check does not validate
the private biological subject mapping.
Every core must receive a final event list, including empty responses and
extraction-failure cores. A final answer cannot be replaced. Six complete fold
receipts join into exactly the existing scorer's `candidate` role; neither its
5-ms matching rule nor its subject-specific F1 vector changes.

## Optical packet

The new source interface has exactly these fields:

- `schema`: `voltron-prepared-optical-traces/v1`.
- `task_id`, `public_sha256`, `preparation_sha256`.
- `movies`: exactly the public 34-movie roster. Every movie has `samples`,
  `amplitude_unit`, `indicator_polarity`, and `exposure_seconds`.

`samples` contains one finite literal integer/float or null per original frame.
Null is allowed only outside declared optical-valid support. Failed extraction
requires a full-length null vector and retains the original clock and cores.
Supported unit labels are `raw_fluorescence`, `delta_f_over_f`, and
`arbitrary_fluorescence`; selecting a label does not authenticate units or apply
any conversion. Polarity is explicitly +1 or -1 and exposure uses the scorer's
exact seconds representation. Their biological/source correctness belongs to
the future independent preparer. Held electrical voltage, injected current,
spikes, private validity and representation-ceiling data have no input field.

The preparer must first qualify patched-cell identity, ROI/background/motion
processing, source units, exposure, optical validity and native clocks. This
packet format does not resolve those scientific prerequisites. The existing
[scope review](../../docs/data-scope.md) documents the original twelve-cell
collection and incomplete signal preparation. The
[native-frame contract](../voltron-native-frame-events-v1/CONTRACT.md) defines
the unchanged output and scoring geometry. Its exact source SHA-256 is checked
before loading the dependency.

## Typed operations

Construct `Session(public, packet, fold_id=..., program_sha256=...,
calibration_sha256=...)` in trusted operator code. The participant-facing methods
are:

- `catalog()`: the complete selected-fold core roster and extraction status.
- `view(core_id, start_frame=..., end_frame=..., low=..., high=...)`: an SVG
  optical view plus explicit frame/clock/exposure/unit/missingness metadata.
- `answer(core_id, frames)`: a sorted unique list of literal native-frame indices
  owned by that core; first final wins.
- `finish()`: requires every selected-fold core and returns an immutable
  snapshot. It closes further views/answers; repeated finish returns a copy of
  the same snapshot.

Every requested frame is represented without resampling, decimation or a
nominal-rate clock. The physical x axis uses the stored native exposure centers.
Each view is bounded to 2,048 frames and the selected core's one-second context
halo on either side, measured in physical time. Larger recordings remain fully
available through additional windows; this is not permission to truncate a
movie or the answer roster. No line bridges missing samples or a positive gap
in optical validity. Failed/missing observations remain visible.

Vertical bounds are explicit view parameters. The component never automatically
normalizes by query values. Out-of-range samples are marked red, omitted from
connecting lines and listed in `clipped_frames`; the caller must request another
gain/window to inspect them. This disclosure does not prove perceptual adequacy.
The original optical vector remains frozen and unchanged for matched numerical
arms. Observation parity and any fixed-image condition require a separately
frozen display/action policy and measured rendering review.

The viewer does not require that the participant inspect every frame before
answering: every core must be answered, while the action log records requested
windows. Availability, requested views and actual visual comprehension are
different facts. No scores or electrical labels are returned.

## Assembly and limits

`assemble_candidate(public, packet, receipts)` requires exactly six unique,
complete fold receipts, one frozen program identity, consistent input hashes,
first-final answer chains and complete native-frame coverage. It returns the
existing role fields `program_sha256`, `calibration_sha256`, and `cores`.
The calibration identity is a deterministic digest of all six declared
fold-specific calibration identities and the public geometry. A protected
operator still has to provide and audit the actual training-only calibration;
this component does not deliver calibration records or verify training.

Receipt hashes detect changes and join artifacts. They are not signatures,
proof of execution, source authenticity or protection against a party able to
fabricate an entire chain. The collector checks logged view geometry and answer
content; it does not replay SVG rendering during assembly or authenticate who
viewed it. Caller-supplied program/calibration hashes are commitments, not a
competent comparator or an isolation certificate.

This is an operator-side Python library. Participant access to its object,
process or filesystem would bypass the intended API boundary. An SVG string
also exposes vector source, so it is not a demonstrated raster-only native
vision condition. Protected transport, rendering/readability, actual memory and
time budgets, calibrated comparators, electrical reference production and
authentic end-to-end execution remain unfinished. No readiness flag or canonical
contract is changed, and this adds zero benchmark registrations.

## Verification

`test_viewer.py` uses invented full-roster optical examples and the unchanged
real scorer interface. It covers nonuniform native clocks, six-fold complete
assembly, wrong-fold access, missingness and failed extraction, explicit gain,
physical halos, duplicate/wrong-core event refusal, immutable first-final
answers and tampered receipts. The tests do not load authentic signals or
electrical references and establish no neural inference accuracy.

Run the generated suite through the project's existing shared test pool, with
`python3 -I -S -B test_viewer.py` as the bounded child command. Integration should
enroll that command for this new component; it must not replace existing event
matching or decoder controls. No new package dependency is required.
