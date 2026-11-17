# BrainVision EEG observation preparation

This component turns a pinned BrainVision recording and an independently frozen
list of sentence sample windows into neural observation files usable by the
NEURAL-065 typed-button task. The existing evaluator only accepted hashes naming
such assets; it did not create or inspect their signal bytes. This preparer reads
binary samples, applies each channel's declared resolution and physical unit,
retains the source loader's non-EOG channel order, and writes finite float64
values in volts. Generated software controls cover both supported binary types,
source byte identity, sample bounds, scaling, layout, and metadata separation.

**This is a preparation component, not authentic neural preparation or a delivered
benchmark.** One authentic header was checked; no recording was processed, no behavioral target was read, and no
model or participant was run in building it. The canonical task and its direct,
viewer, tool-assisted and frozen-program access statuses remain unchanged.

## Scope and source

The [official V1 loader](https://github.com/facebookresearch/brain2qwerty/blob/5f9889621d0df391c5aab37c996683d308e6e926/studies/spanishbcbl.py)
loads EEG with `mne.io.read_raw_brainvision`, excludes channel names containing
`EOG`, and sets a standard montage. The data revision is
`88f9096c6ce3a3fb17cc7b8e3131ff7f96da5684`. Only that EEG route is implemented;
MEG FIF and V2 are outside this component. Source code facts were inspected from
an existing pinned local cache; no author code or data is redistributed here.
The pinned public `002_DECOMEG_S1_9696_task1.vhdr` header was fetched and parsed:
11,703 bytes, SHA-256
`04e401f904a291bfaf1a0a1f386cf0375a2de5a82e32cd1a0f7ac1ac062c178d`.
It declares 64 channels at 1,000 Hz, multiplexed `INT_16`, and 0.1 microvolt per
stored count; 61 channels remain after excluding the three EOG channels. This
checks a real header profile, not sample integrity, population coverage or
successful neural preparation. The external receipt retains the source URL and
acquisition accounting; the raw header remains outside Git.

The reader supports BrainVision 1.0 binary multiplexed little-endian `INT_16`
and `IEEE_FLOAT_32` recordings. It requires explicit positive channel resolution
and voltage units (`V`, `mV`, `uV`, or a micro-sign spelling), converts to volts,
and rejects unsupported formats, nonfinite selected samples, incomplete frames,
and out-of-bounds windows. `SamplingInterval` is interpreted in microseconds.
The declared channel roster must exactly match every non-EOG source channel in
source order; this component does not choose a favorable channel subset.

These are raw observation windows. There is no resampling, filtering, baseline
correction, clipping, interpolation, standardization, fitted scaler, bad-channel
correction, or source-decoder preprocessing. The author's MEG feature recipe is
not reproduced by this EEG reader. Ocular/motor contributions remain possible.

## Frozen input and operator use

Use an existing Python 3.9+ runtime; the implementation has no third-party
dependencies. Before authentic execution the operator must independently pin
the source payloads, reconcile person/session identities, and freeze the selected
cohort, complete eligible sentence inventory, split, alignment/exclusions and
sample windows. Native preparation still requires the wave's resource protocol.

The private plan is UTF-8 JSON with exactly these keys:

```json
{
  "schema_version": 1,
  "task_id": "NEURAL-065",
  "source_commit": "5f9889621d0df391c5aab37c996683d308e6e926",
  "data_commit": "88f9096c6ce3a3fb17cc7b8e3131ff7f96da5684",
  "recording_subject": "Pinet2024Eeg/002",
  "session_id": "session1",
  "selection_sha256": "<externally frozen selection digest>",
  "alignment_evidence_sha256": "<externally audited alignment digest>",
  "channel_names": ["<all non-EOG source names, in source order>"],
  "windows": [
    {"query_id": "<opaque 32 lowercase hex characters>", "start_sample": 100, "stop_sample": 400}
  ]
}
```

This is a schematic, not an authentic selected subject or sampling proposal.
Window bounds are zero-based sample indices into the BrainVision file; intervals
are half-open `[start_sample, stop_sample)`. Behavioral and neural clocks must be
reconciled **before** deriving these bounds. This program neither estimates DTW
nor silently interprets seconds as samples. Fractional-sample rounding, context
duration, template families and allowed event assistance belong in the frozen
operator protocol. Overlapping distinct windows are retained as declared; their
split/privacy implications still require operator review. Duplicate IDs,
duplicate intervals and duplicate resulting observation bytes are refused.

```sh
python3 prepare.py \
  --header /operator/source/recording.vhdr \
  --data /operator/source/002_DECOMEG_S1_9696_task1.eeg \
  --plan /operator/private/frozen-windows.json \
  --header-sha256 HEADER_SHA256 --data-sha256 DATA_SHA256 --plan-sha256 PLAN_SHA256 \
  --max-source-bytes FROZEN_SOURCE_BYTE_LIMIT \
  --max-output-bytes FROZEN_OUTPUT_BYTE_LIMIT \
  --output /operator/export/observations
```

Hashes identify exact file bytes and must come from independent frozen evidence;
supplying hashes calculated from an unauthenticated file does not establish its
authenticity. The `.eeg` file must be beside its header, match the header's literal
data basename, and match the plan's subject/session and a typing-task filename.
Final source symlinks and non-regular files are refused. Header and plan reads
are bounded to 64 KiB and 4 MiB. Source hashing and extraction use bounded chunks;
source bytes are hashed again after extraction to detect concurrent modification.
The output byte budget applies to neural arrays, with small manifest/receipt
overhead in addition. Runtime is linear in the two full-source hash passes plus
all selected sample frames. No imports or reads of behavioral logs occur.

## Outputs and integration

The new participant directory contains only:

- `observations.json`: opaque case IDs, asset paths/hashes, dimensions, sample
  frequency, relative-time convention, synthetic channel IDs, dtype, byte order
  and volts as the physical unit.
- `assets/ID.f64le`: little-endian float64 samples in **time × channel** row-major
  order, without headers, comments, keycodes, source filenames or target labels.

For sample `i` within a window, its relative time is `i / sampling_frequency_hz`.
Absolute recording clocks and sample offsets are omitted from participant
metadata. Synthetic channel IDs preserve source order; the private receipt maps
them back to source names/resolutions. This component does not provide electrode
coordinates or a verified shared cross-person sensor map; those must be added
through a reviewed allowlist when the participant protocol requires them.

Private provenance is written beside the participant directory as
`observations.private-receipt.json` with mode `0600`. It contains the original
plan, source identities, channel metadata, exact hashes, dimensions and byte
counts. **Do not expose the parent directory or receipt to participants.** The
staging directory is removed on extraction failure; existing output and receipt
paths are never overwritten. A publication failure after receipt creation may
leave that private receipt, requiring operator reconciliation before retry.

For every selected sentence, copy the emitted `neural_asset_sha256` into the
existing evaluator packet's corresponding opaque `query_id` row. Freeze the
completed private packet only after all selected recordings are prepared, then
use the existing evaluator's `query_manifest()` and packet digest to bind
submissions. Its alias, biological visit, template, calibration, exact-ID and
CER checks remain required. This preparer covers one source recording per call;
it cannot establish the full multi-person task by itself. Training/calibration
labels and direct/viewer/tool/program participant transports remain separate
unimplemented delivery work. Raw-array availability is not direct interpretation
or viewer-delivery evidence.

## Validation and remaining limits

`tests/test_prepare.py` uses generated BrainVision files only. The independent
numerical oracle verifies nonzero frame offsets, per-channel scaling and
time/channel layout; additional controls reject malformed source profiles,
wrong hashes, changed source bytes, unsupported identities, bad window plans,
metadata leaks, duplicate content and nonfinite samples. The CLI is exercised.
In the active parallel wave, run tests only through the shared test pool.

Authentic payload compatibility, complete selected cohort and alignment,
physical visits, signal/model reference execution, matched language-only
competence, protected evaluation and scientific admission are unestablished.
No task/contract/registry readiness field is changed.
