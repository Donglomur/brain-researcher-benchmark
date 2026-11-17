# Whole-person sleep waveform viewer

This adds a typed waveform-viewing path for the **existing 5,450-epoch sleep
development panel**. The participant sees signal images and the permitted clock
metadata, navigates within the current person, and supplies five probabilities
for every epoch. A collector replays both complete histories and writes the
unchanged finite sleep scorer's submission format.

**Current evidence is generated software controls and authenticated source
metadata only.** No authentic waveform was read or rendered by this component's
construction, and no model/provider session was run. The task's current
unsupported direct/viewer status is unchanged. This is viewer-mediated
interpretation source, not delivery of a no-tools condition or a scientific result.

## Original inputs and cases

`SOURCE_FACTS.json` records the exact existing raw packet hashes and source
processing facts recovered from the earlier raw-development export. Its status
fields describe that metadata inspection, not a new execution. Required packet
members are exactly `manifest.json`, `clock.npz` and `signals.npy` for each person:

| Person | Complete epochs | Samples per channel | Signal file bytes |
| --- | ---: | ---: | ---: |
| development-001 | 2,780 | 8,340,000 | 200,160,128 |
| development-002 | 2,670 | 8,010,000 | 192,240,128 |

Signals retain all three original channels—EEG Fpz-Cz, EEG Pz-Oz and horizontal
EOG—at 100 Hz, C-order float64 volts. The original export used calibrated EDF
microvolts multiplied by 1e-6, with no filtering, resampling, label-based crop or
dtype reduction. These already existing packets avoid another EDF conversion.
Historical export/auditor receipts reported complete identity and clock equality
with the finite feature programme; this revision inspected metadata, not the raw
payload. Runtime construction hashes all signal bytes and checks headers before
mapping them read-only. It verifies the pinned clocks separately and never reads
labels, score masks, training packets or YASA predictions.

IDs are `development-001/00000` through `/02779` and
`development-002/00000` through `/02669`. Unknown or movement epochs remain in the
input and response roster. Only the separate original grader applies private
scoring masks. Both people were already exposed during benchmark construction.

## Viewer condition

The condition is `whole_person_raw_viewer_zero_shot`. It supplies no labelled
demonstrations or human feedback. The default view contains all three channels
and all 3,000 samples of the selected 30-second epoch. Every visible sample and
adjacent segment is drawn; finite large amplitudes are geometrically clipped at
the display boundary and flagged. Gain changes the display, not the underlying
signal. Time axes are seconds from the original whole-recording origin. Clock
features retain their original float64 values in response metadata; image labels
are rounded for readability.

| Action | Fields and behavior |
| --- | --- |
| `inspect` | Render the current view. |
| `epoch` | Integer `index`; select any epoch in this person and reset the view to its full 30 seconds. |
| `window` | Integer `start_sample`, `stop_sample`; display a half-open interval of 100–6,000 samples anywhere in this same person. The target epoch stays fixed. |
| `gain` | `microvolts_per_division`: 10, 20, 50, 100, 200, 500 or 1,000. |
| `channels` | An ordered nonempty subset of the original three names. |
| `respond` | Exact current `epoch_id` and five `probabilities` in W, N1, N2, N3, R order. |
| `finish` | Close only after every epoch has its first valid final response. |

Before a response is accepted, the target's complete three-channel interval must
have been rendered at least once. Subsequent zooming and channel inspection are
allowed. The window and gain limits are explicit implementation choices, not
properties reported by the source study. **All future and past context within
the current person remains accessible** through navigation. Previous self-created
responses may persist within that person's session; no cross-person state is
permitted by the study design. A separate fresh viewer process is needed for each
person. The external provider/controller must also enforce fresh model state.

The operator sets a finite action budget before the session. Minimum completion
requires `2 * epochs + 1` actions; the implementation caps a session at 100,000.
This cap does not select a study budget or establish matched compute. A future
study must freeze its actual observation, action, token and time budgets.

The source renderer reuses the unchanged, pinned EEG viewer raster primitives.
Sleep-specific rendering and its PNG codec are local to this component; the EEG
source is not altered. The local codec losslessly compresses the exact RGB pixels
at the same 1,400 × 820 resolution with fixed zlib settings. Four generated
examples shrank from 3,445,148 bytes each to 16,008–46,423 bytes; all decoded
scanline bytes matched. Measured codec CPU was 0.039–0.225 seconds per call on
those examples. These are generated-image measurements, not observations about
authentic sleep data or an executed full study. Raw sample values and source filenames never appear in
the participant projection. PNG signals plus exact public clock metadata are
different from numerical raw-array access.

## Operator entry points

Python 3.11 or later and NumPy are required. `SOURCE_BINDINGS.json` authenticates
the unchanged raster and original five-class submission validator. The checkout,
operator and dependency runtime remain trusted inputs. No network, install,
download, model call or label access is performed by these commands.

Each packet directory must contain only its three pinned public members. Use a
fresh output directory outside the checkout. The following action budget is an
illustrative command argument, not an executed or qualified study protocol:

```sh
python -I -B benchmarks/neural/NEURAL-007/implementations/whole-night-viewer-v1/viewer.py serve \
  --case development-001 --packet /operator/person1/packet \
  --max-actions 20000 --output /operator/evidence/person1-viewer
```

Send one JSON action per stdin line and consume one JSON response per stdout line
after the initial instructions. Signal views contain PNG images encoded as
base64. The provider adapter must decode and attach them as image content, never
present the base64 string as prose. A restricted participant transport must expose only these typed actions
and projections, never this operator process's filesystem or Python interface.
Run development-002 separately with its own packet and fresh model state.

```json
{"action":"epoch","index":0}
{"action":"respond","epoch_id":"development-001/00000","probabilities":[0.2,0.2,0.2,0.2,0.2]}
```

`manifest.json`, the hash-linked action log and `completion.json` remain in
operator custody. Invalid input or early EOF writes a best-effort `failure.json`
with the bounded exact last input, its hash, possible truncation/EOF, consumed
action counts and error. A failure marker forbids collection, even if a completion
file is also present. Keep outer stderr/exit capture for failures that prevent
writing evidence, such as full storage. Source and Python/NumPy/zlib version
identities are captured; version strings do not authenticate package binaries.
Collection requires the same declared versions and source,
re-authenticates both raw packets and re-renders every observation to verify the
exact recorded responses:

```sh
python -I -B benchmarks/neural/NEURAL-007/implementations/whole-night-viewer-v1/viewer.py collect \
  --packets /operator/person1/packet /operator/person2/packet \
  --sessions /operator/evidence/person1-viewer /operator/evidence/person2-viewer \
  --output /operator/evidence/sleep-viewer-collection
```

The resulting `predictions.npz` includes the fixed class order and all 5,450 IDs
and probability rows. The unchanged original validator checks it under the
task's stricter **4,000,000-byte** limit. No probabilities are normalized or filled
in. The separate portable grader can subsequently evaluate the frozen output;
this component never opens its targets or computes a scientific score.

Images are generated on demand and are not retained in these logs. Collection
repeats rendering, so CPU, bandwidth and provider image limits must be measured
under a future authentic protocol. Generated-trace codec measurements do not
establish authentic-waveform compression or provider feasibility.

## Limits of the comparison

Matched identities do not imply matched information. This viewer offers raw
EEG/EOG images and clocks without training examples; the existing programme
offers engineered features, six training people's labels and a separate
pretrained-model access condition. An overall capability comparison may use the
same target panel, but it cannot isolate the causal effect of tools without an
additional information-matched design. Two exposed people support descriptive
per-person results, not population inference or untouched-holdout claims.

Replay establishes internal source/input/action/response consistency. A trusted
host could fabricate a history; hashes do not prove model authorship, that a
remote model saw each image, isolation or meaningful interpretation. Provider
transport, authentic full-panel runtime costs and a controlled model comparison
remain unqualified. Preserve failures and exact exposure history.

Generated checks exercise header/clock/channel mapping, future-context access,
complete observations, first-final-response rules, malformed actions, altered
histories, real generated PNG serve/replay, and all 5,450 generated responses
through the unchanged validator. They contain no scientific observations.

```sh
python -I -B benchmarks/neural/NEURAL-007/implementations/whole-night-viewer-v1/test_viewer.py
python -I -B benchmarks/neural/NEURAL-007/implementations/whole-night-viewer-v1/test_render.py
```
