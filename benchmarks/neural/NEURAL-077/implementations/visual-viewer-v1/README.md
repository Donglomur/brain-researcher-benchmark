# NEURAL-077 visual trace condition

This component lets an agent inspect authentic Cz/Pz ERP epochs through PNG
trace images and a bounded viewer API. It is a visual input condition for the
existing target-stimulus probability task. It is **not seizure detection**, a
replication of the reported mouse EEG viewer experiment, or evidence of model
performance. No new model trial was run.

The output remains exactly `{"trial_id":"<current query ID>","target_probability":0.25}`.
The existing complete two-case NPZ validator is reused unchanged. The canonical
scorer remains equal-person balanced accuracy at threshold 0.5, with
natural-log loss secondary. This package neither reads targets nor scores.
There is no scientific pass threshold and no requirement that a candidate
inspect particular channels, examples or intervals before answering.

## Two explicitly separate conditions

| Mode | Available visual input | Interpretation |
| --- | --- | --- |
| `zero_shot` | One unlabelled query; no examples or feedback | Fresh-context zero-shot episode |
| `four_demo` | Same query plus the original four labelled training demonstrations | Demonstration-assisted episode, never zero-shot |

The demonstrations are deliberately balanced. Their fraction does not estimate
the target prevalence; no numerical population prior is supplied. No other
training labels are available. Neither mode reveals the query answer, provides
feedback, or permits another evaluation query in the session. Sequential
feedback is a separate prospective experiment and is not implemented here.

Both modes cover the same 400 previously exposed development trials, 200 from
each of two people. They are not unseen-population evaluation. The existing
numerical waveform and programme conditions have different representations and
processing permissions; sharing source epochs does **not** imply identical
information. Raster quantization, clipping, navigation and processing access
can explain future differences, so a comparison cannot attribute a gap solely
to "understanding". Blinded humans can use the same prompt, actions and images,
with the condition and navigation history recorded identically.

## Authentic source reuse

`SOURCE_BINDINGS.json` pins `complete-direct-condition-v1` from ancestor
`8870430108dd61d1d6661b09198708e82cc7178d`. That package pins the existing waveform
exporter, scalar parser, registered NPZ validator and public asset manifest.
The viewer authenticates all five original public packet files, checks the
complete 400-query roster, then selects one query. It reuses that route's
commitments; it does not invent another normalizer or silently rescale samples.

The earlier complete delivery independently recomputed all 400 queries and four
demonstrations from pinned 33-channel float32 arrays, using float64 rereferencing
and baseline subtraction. The viewer reads the identical committed processed
packet; it does not read raw 33-channel files or repeat their normalization.
It does not trust the delivery's `COMPLETE.json` as input authority. No authentic
signal files, rendered authentic images or model responses belong in public Git.

The dependency package must be present in the integrated repository. Before
integration, a trusted operator can supply `--implementation-root` pointing to
the existing committed sibling implementation tree. All imported dependency
bytes are checked against pins. This flag is not a participant action.

## Display semantics

- All 1,024 samples per channel are retained at 1,024 Hz. Sample offsets run
  from −256 through 767; the full support is `[−256,768)`, or `[−250,750)` ms.
  The final sample is at 749.0234375 ms. Offset zero is array index 256.
- Cz and Pz were rereferenced to `(P9+P10)/2` and each epoch/channel had the
  mean of offsets −256 through −1 subtracted by the original source route.
  The released marker's physical display-delay correction remains unresolved.
- Amplitude is **native stored EEG amplitude**, with independently calibrated
  microvolts unresolved. Positive values point up. Gain is native units per
  30-pixel division, shared by selected channels; it changes only the display.
- Every visible sample and every adjacent piecewise-linear segment is rendered.
  There is no stride decimation, bin averaging, interpolation of additional
  samples, or automatic rejection. The 1,120-pixel plot width exceeds the
  1,024-sample maximum window. Finite raster resolution still limits perception.
- Segment crossings are geometrically clipped at ±3 divisions. The image warns
  `CLIPPED: INCREASE UNITS/DIV`; no hidden auto gain is applied. Very small amplitudes
  can be subpixel until gain is adjusted. Zoom uses the same original samples.
- No additional display filter is provided. On these one-second processed epochs,
  an arbitrary filter would add edge assumptions and change the visual condition.
  `display_filter: "none"` is recorded in every frame. Montage is fixed to the
  committed rereference; the two-channel packet cannot support other montages.

The PNG renderer uses a source-defined bitmap font, integer line rasterization,
fixed RGB pixels and stored DEFLATE blocks. It does not depend on a GUI, external
fonts, a plotting library, timestamps or compressor-version heuristics. PNGs
contain only IHDR/IDAT/IEND chunks. No SVG trace coordinates or numerical sample
payload are returned. Pixel and PNG bytes are repeatable for the same inputs.

## Typed actions and terminal capture

`actions.schema.json` describes the available action objects. `viewer.py`
additionally enforces exact Python types, no duplicate JSON fields, finite
numbers, state bounds, condition-specific record availability and byte limits.
Booleans cannot substitute for integer offsets or gains.

| Action | Parameters and semantics |
| --- | --- |
| `inspect` | Render the current state. |
| `select` | `record`: `query` or `demo1`…`demo4` (demos only in `four_demo`); resets to full epoch and retains gain/channel selection. |
| `window` | Integer `start_sample`, `stop_sample`; half-open native offsets in `[−256,768)`, at least 16 samples. |
| `scroll` | Nonzero integer `samples`; moves the window exactly and rejects overrun. |
| `zoom` | `factor`: 2 (in) or 0.5 (out); integer `center_sample` in current window. Width rounds to nearest integer (ties to even) if needed, remains 16…1,024 samples, and the window shifts to fit at epoch boundaries. Returned bounds are authoritative. |
| `gain` | `units_per_division`: one of 1, 2, 5, 10, 20, 50, 100, 200, 500, 1,000. |
| `channels` | `channels`: `["Cz"]`, `["Pz"]` or `["Cz","Pz"]`. |
| `finalize` | `response`: the exact raw model-returned JSON text, at most 4,096 UTF-8 bytes. |

No action accepts a filesystem path, executable code, detector, sample request,
raw-array export, arbitrary filter expression, or target lookup. Each rendered
response includes only PNG image bytes, view metadata and the selected training
label when permitted. Source identifiers, packet hashes, process receipts and
logs remain operator-side.

The CLI emits an initial overview, then accepts one JSON action per line, up to
8,192 bytes per request and 128 total actions including that overview and final
submission. Invalid bounded requests consume an action and are recorded
losslessly, including malformed UTF-8. An oversized request, exhausted budget
or transport EOF leaves a failed/incomplete session. A well-formed `finalize`
locks the session immediately, preserves the first exact response bytes, and
creates `FINAL.json` even if the scalar response is invalid. No correction or
replacement final response is accepted. Malformed action envelopes are rejected
before they constitute a final response.

Outputs use exclusive creation in a fresh operator directory. Every action has
a sequence number, previous-record hash and raw request commitment. PNGs and
metadata are bound to the action; final capture binds the chain and session.
`collect` replays every accepted action, rerenders and checks each stored frame
and metadata, verifies the actual prompt and first final response, and requires
all 400 query sessions for one mode before writing the unchanged NPZ layout.
Missing, duplicate, foreign, mixed-mode, altered, invalid or failed sessions
cannot produce a complete submission. The collector does not skip failures,
retry requests or choose a favorable answer.

## Trusted operator usage and transport boundary

The additive [restricted transport](../visual-transport-v1/README.md) now
provides raw PNG framing, complete wire capture, explicit episode limits,
fresh participant processes, an exercised local macOS client sandbox, and
complete400 collection through this viewer. Its local scripted controls do
not qualify any remote model/provider or establish model performance. The
standalone viewer CLI below still requires an operator-supplied transport.

Python 3.11+ is sufficient for rendering and generated controls. The authentic
source loader and NPZ collection also require NumPy because the reused public
validator imports it. Under `-I`, NumPy must be installed in that interpreter or virtual environment, not only its user-site directory. Use an existing environment; no install or download is
performed. Run from a trusted ordinary directory with no concurrent hostile
writers, and supply a fresh output directory under an existing parent:

```sh
python3 -I -B viewer.py serve \
  --packet /absolute/existing/authentic-delivery/public \
  --ordinal 0 --mode zero_shot \
  --output /absolute/operator/sessions/000
```

Standard output is newline-delimited JSON. The first message contains the
scientific prompt, action schema and initial image result. The trusted transport
must decode `image.base64` and deliver an actual image content block to the
vision model, together with permitted display metadata; **do not present the
base64 as prose**. Forward participant action JSON to stdin and return the
bounded result. Error text on stderr, source files, output paths, session logs,
raw packets and the process environment are not participant content. A custom
adapter may use `Session.handle` with the same projection and supply its initial
`inspect`; the API intentionally also records an immediate answer if the
candidate declines to inspect, rather than excluding that attempt from results.

The renderer produces 1,400×820 RGB PNGs of approximately 3.45 MB each (4.60 MB
in base64). At 128 actions the maximum image storage is under 442 MB per session;
a session spending one action on finalization emits at most 127 frames. A full
400-session campaign may therefore use substantial storage/bandwidth. These
are software bounds, not measured platform limits. No image-size compatibility
or context capacity has been qualified for a model transport.

For each mode, retain exactly one directory `000` through `399` in the sessions
root, including failed attempts. After all attempts have terminal records:

```sh
python3 -I -B viewer.py collect \
  --packet /absolute/existing/authentic-delivery/public \
  --sessions /absolute/operator/sessions --mode zero_shot \
  --output /absolute/operator/new-admission
```

Actual visual-only isolation requires the **harness** to expose only this viewer
and terminal response tool, deny file/shell/code/retrieval/raw-packet access,
start each query with fresh model context, and prevent other-query memory.
This local Python component and its hashes do not establish that boundary.
They also cannot prove what a remote service received, detect omitted upstream
attempts, stop a privileged operator rewriting all evidence, or protect a
shared-host filesystem. Such deployment remains unqualified. No prompts or
hashes are described as a security sandbox or cryptographic attestation.

## Verification

```sh
python3 -I -S -B -m unittest discover -s . -p test_viewer.py -v
python3 -I -B -m unittest discover -s . -p test_native.py -v
```

Generated controls cover exact time/sample/channel geometry, one-sample
transients at full view and zoom, correct clipping crossings, deterministic PNG
bytes, PNG CRC/pixel decoding, prohibited actions, JSON/type bounds, demo
separation, immutable invalid final capture, lossless rejected requests,
recomputed frame/metadata/prompt checks, incomplete population refusal, and a
complete invented 400-session NPZ collection through the unchanged validator.
Generated scalar fixtures are not solver trials.

Separate local operator evidence authenticates the complete existing packet and
renders fixed ordinals 0 and 200 plus all four training demonstrations. No query
labels, prior solver outputs, fitted models, scoring, model APIs or downloads
are involved. Authentic images stay outside the repository. This establishes
engineering behavior on available ERP inputs; it supplies no viewer model
result, mouse-seizure data access, human-equivalent claim or task qualification.
