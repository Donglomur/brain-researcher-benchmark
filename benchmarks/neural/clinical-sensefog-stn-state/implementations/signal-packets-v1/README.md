# SenseFOG native signal packet projection

This operator component fills the gap between the complete recording-grid lag
mapper and physical waveform observations. It preserves the existing task,
mapper and scorer. It constructs no clinical labels, runs no decoder and does
not qualify any model access mode.

`project_packets(grid, signal_metadata, aliases, read_segment, *, max_cases,
max_packet_values, max_total_values, max_output_bytes)` consumes the same
`sensefog_target_free_pairing_input_v2` grid as the existing scorer. All twelve
participants, original recording-grid cases, complete channel sets and twenty
fixed lag requests are validated by the unchanged pinned mapper. Python 3.11+
standard library is sufficient.

## Frozen operator declarations

`signal_metadata` has exact fields `schema="sensefog_signal_metadata_v1"`,
`task="clinical-sensefog-stn-state"`, `grid_sha256` and `segments`. The grid hash
uses sorted compact ASCII JSON with nonfinite values prohibited, identically to
the existing scorer's `canonical_sha256`.

Every observed segment has one metadata row with `segment_id`, `signal_sha256`,
`calibration_receipt_sha256` and `channels`. Each channel has `channel_id`,
`hemisphere` (`left` or `right`), `physical_unit` (`V`, `mV` or `uV`) and
`montage`. Channels retain the exact declared source order. Every montage must
account for both hemispheres, without assuming that the release has two channels.
The montage text must describe the original reference/contact derivation and be
audited as target-free by the operator. Its bounded character syntax cannot
establish semantic absence of a participant, protocol or state cue.

The source and calibration hashes are **declarations**, not authentication of
the reader, units, calibration, filtering, acquisition clocks or complete release.
This component cannot determine whether a scale factor or montage description is
correct. Do not invent these operands from a nominal device specification.
An unsupported electrical unit or unauthenticated/unilateral source montage must
be resolved separately, not converted or padded to pass this interface.

`aliases` maps every original case ID to a unique 32-hex-character case token.
The operator must select independent opaque aliases before outcomes and reuse
the same mapping across arms. A syntactically valid token does not establish
entropy or anonymity. The mapping remains private.

`read_segment(segment_id, tuple(channel_ids), local_start, local_end)` returns
channel-major Python lists for exactly the half-open native segment interval.
Values are already calibrated in each declared physical unit. Every non-missing
sample must be a finite number, excluding booleans. Missing-mask samples must be
explicit `None`. Artifact flags are retained alongside finite measurements;
they do not automatically remove windows. The reader performs no interpolation,
resampling, filtering or normalization on behalf of this component. Its actual
I/O and preprocessing dependencies must be independently qualified against the
declared causal lookback. No source-file parser or native reader is supplied here.

Caller declarations are snapshotted before the callback. Each distinct requested
segment interval is read once without retries or unsupported-case substitution.
Returned buffers are copied before another callback can mutate them.

## Complete scope and separation of substrates

Each original case has an `original_core` record for the native two-second
window. This remains independently available when training dependence or a
longer authorized lookback is unavailable. A second
`original_authorized_support` record covers the complete declared causal H-sample
support, with the two-second core at its end. If H is unknown or the required
history crosses a boundary, this record is explicitly unavailable; the core and
the original case remain in the census.

Every one of the twenty fixed lag maps also has a record. Supported maps use
the mapper's exact complete donor-support interval, and all channels move by
the same lag. The existing full-support missing/artifact-mask match is retained.
Unsupported maps receive a reason and no packet. They never receive unchanged
original input, circular wrapping, gap stitching or a replacement window.

Core-only and complete-lookback observations are different substrates whenever
H exceeds two seconds. Compare original complete support with lagged complete
support on identical supported cases. Do not compare a core-only original to a
history-enriched transformed/specialist packet and call it an equal-information
tool effect. An unavailable support packet is extraction coverage, not an
automatic primary exclusion or a clinical target status. Protected label and
failure policies remain the existing scorer's separate responsibility.

## Output custody

The returned `sensefog_operator_packet_projection_v1` object is entirely
**operator-owned**. Its `private_manifest` retains original IDs, participants,
recordings, source segments, control identities, all availability reasons and
packet hashes. Do not give this object, the aliases, metadata, source reader or
maps to a participant.

An individual `packets[sha256]` value is the proposed public observation. It
contains only the case token, native sample rate, relative sample origin, core
indices, ordered channel tokens, hemisphere, physical unit, explicit montage,
values and complete missing/artifact masks. Time is
`(relative_sample_start + index) / sample_rate_hz` seconds relative to core onset.
It exposes no structural fields for original time, participant/session,
recording/segment, donor identity, lag multiple, clinical label, IMU or EMG.
Permitted montage descriptions still require the semantic audit above.

An external participant transport must serve only the authorized packet and
matched training evidence. This module does not provide that transport, filesystem
isolation, a viewer, a no-tools boundary, hidden-state enforcement, a response
collector or model provenance. A source packet dictionary is not evidence of
native neural understanding. Packet equality can support later equal-arm byte
checks; it does not establish clinical authenticity or a qualified benchmark.

## Bounds, validation and remaining work

Per-packet and complete unique-reader value caps are checked before callbacks.
The full JSON byte cap is checked after construction; an exceeded cap rejects
the whole operation. There is no partial-cohort export. The function materializes
maps, slices and output packets, so these are logical caps, not OS memory/time or
physical-I/O limits. A callback/output-cap failure can occur after source reads;
those failed attempts must remain recorded. The API writes no files and returns
no partial result. It is an operator helper, not a hostile-callback sandbox.

`test_packets.py` exercises complete twelve-person coverage, three channels,
synchronized native lags, history/gap boundaries, full masks, strict declarations,
source-reader shape and numerical failures, pre-read caps, failed output caps,
and mutation protection. Its generated two-Hz recordings are not clinical data.
Run `python3 -I -S -B test_packets.py` through the shared construction pool.
The source files must be enrolled in the repository's component/CI inventory
before being treated as maintained public implementation.

The original [author documentation](https://github.com/PKlocke/SenseFOG-Documentation)
describes selected walking, turning, stopping and freezing intervals. Unannotated
time cannot therefore be silently relabeled as ordinary walking. This projector
does not infer any clinical category or apply those original episode-selection
rules to the proposed continuous benchmark.

Remaining requirements include the complete original release census, native
signal reader, clinical-clock reconciliation, authenticated calibration/montage,
prospective classes and boundary/exclusion policy, frozen independent references,
event metrics, complete candidate delivery and actual same-case evaluations.
No authentic recordings, clinical targets, models or paper results were run for
this component. Task count, existing canonical contracts and readiness are
unchanged.
