# Raster delivery for the complete NEURAL-084 viewer

This source component converts the accepted typed waveform viewer's SVG into
PNG pixels and binds each response to a fixed operator transport callback. It
reuses the accepted complete54-fold `Panel`; it does not introduce another
collector, prediction schema, process supervisor or scientific endpoint.

`RasterPanel(folds, transport, max_requests=..., max_capture_bytes=...,
max_delivery_bytes=...)` accepts the same54 ordered fold records and existing
viewer/provider source operands. The operator calls `open_next` with the exact
training metadata and trusted epoch providers. Participants use the original
`information`, `training`, `begin_queries`, `view`, `answer` and `finish` JSON
actions through `dispatch(raw_bytes)`. The original Panel checks every action
and preserves21200 donor rows,400 query rows,128 views per epoch, irreversible
training retirement, first-final answers and the all54-fold export barrier.

The fixed callback receives two arguments:

- Canonical JSON metadata bytes with schema `neural084-raster-delivery-v1`, a
  sequence number, original action, allowlisted response metadata, and either
  no image or a PNG descriptor containing byte count, SHA256 and dimensions.
- PNG bytes for a waveform response, otherwise `None`.

The callback must return exactly `True` after accepting that response. This is
an acknowledgement of the operator call; it does not establish what an external
model received or understood. `dispatch` returns only an operator acknowledgement.
SVG, polyline coordinates, waveform arrays and arbitrary host objects are never
passed to the callback. Original public frequencies and labels for training
examples remain permitted metadata. Query responses do not contain labels.

An ordinary rejected original action keeps the original Panel behavior. A
rendering, schema, output-budget or callback failure after a consumed response
makes this owner terminal. Further actions, new folds, completion and prediction
exports are blocked. Reentrant transport-callback calls are also terminal. This
guard starts after Panel handles the action; arbitrary trusted provider callbacks
remain outside that guard. Bytes attempted
through a failed callback stay charged. There is no automatic retry or replay.
The API is trusted operator code: callers must not retain and expose its private
underlying Panel or provider references to a participant.

## Rendering and reuse

The renderer accepts only the exact source-pinned N084 SVG grammar. It preserves
1000-pixel width,86-pixel lanes, channel order, two-to400 source-sample windows,
all selected sample centers, the common full-epoch amplitude bound, and the
physical-unit-unverified annotation. It validates finite bounded coordinates
before drawing; no sample is dropped. Every original SVG point is rounded to
the nearest integer pixel and adjacent points are connected using the reviewed
integer line primitive. No numerical EEG filtering, recentering, interpolation
of signal values, resampling or normalization is introduced.

The exact reviewed `NEURAL-EXP-005/typed-raster-viewer-v1/viewer.py` supplies only
its bitmap Canvas, line, text and PNG encoding primitives. It is captured by
hash into an isolated module with width1000. Four fixed glyphs (`[`, `]`, `|`, `,`)
complete the original N084 annotations. Its Helsinki packet parser, Session,
rendering policy, channels, time windows, scale and clinical endpoint are never
invoked. No supervisor is copied. The PNG contains only IHDR, IDAT and IEND;
there is no embedded SVG, raw waveform text or ancillary metadata channel.

Bitmap labels use uppercase14-pixel-high glyphs. The strict renderer rejects
unsupported or clipped labels instead of substituting question marks. This
font and integer-pixel quantization differ from the original SVG's fonts and
vector rendering; identical scientific source support does not establish equal
perceptual information. The retained generated images support inspection of
this implementation, not authentic EEG readability or native understanding.

## Completion and limits

`finish_collection()` still requires all54 first-final folds. It produces a
separate unqualified raster receipt binding the original collection receipt,
acknowledged-message count, PNG count, attempted bytes and transcript hash.
`candidate_prediction(fold)` remains unavailable before complete collection.
This is not programme `COMPLETE.json`, `GRADE_HANDOFF.json` or evidence of270
native closures. Complete CCA, constant and frequency-permuted outputs,
protected pool/gold, source provenance and scoring remain separate prerequisites.

The caller supplies explicit whole-panel request, capture and delivery limits.
Individual metadata responses are capped at16384 bytes and PNGs at4MiB. These
are software accounting limits, not OS memory, process-time or network bounds.
The callback controls external transport and remains trusted. No filesystem,
network, remote-provider or model-context isolation is established here; fresh
FoldViewer objects alone do not reset participant memory between folds.

Authentic OpenBMI preparation, provider/source authentication, full54-fold
execution, external participant/model identity and native image-only study
admission remain unqualified. A PNG can be analyzed by tools; delivery format
alone cannot establish a no-tools/native condition. No ready count or model
performance claim is introduced.

## Generated controls and integration

`test_delivery.py` contains eight new controls: actual pixel/PNG delivery,
independent RGB/chunk/CRC decoding, all400 rendered sample positions and common
scale, full and zoomed image evidence, last donor-row access and retirement,
first-final and partial-export behavior, terminal renderer/callback failures,
delivery budget/reentrancy, and rejection of unsupported or dangerous SVG
grammar. Only generated small epochs and metadata are used. The test opens
fold001 and does not run a complete fold or full panel. Accepted historical
viewer/Panel suites are not replayed.

After dependency integration, run `python3 -I -S -B test_delivery.py` from this
directory. In the private package, `NEURAL084_SOURCE_IMPLEMENTATIONS` identifies
the exact dependency implementations root and `NEURAL084_CANVAS_SOURCE` the
exact reviewed Canvas source. Optional `NEURAL084_RASTER_EVIDENCE` names a fresh
directory for two PNG files, each capped at128KiB. No original-data access is
needed. Sole integration owns explicit CI enrollment and selection of the
accepted private Canvas/viewer/Panel dependencies; their presence is not assumed
at the immutable base.
