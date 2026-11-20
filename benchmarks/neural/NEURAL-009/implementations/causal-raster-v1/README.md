# Causal EEG raster delivery

This inactive operator component adds PNG-only view replies to the existing
`causal-presentation-v1` `Cohort`. It preserves that component's case identities,
causal windows, actions, irreversible 10 Hz answers, failure ledger and complete
candidate interface. The original typed SVG route and canonical seizure scorer
are unchanged. No participant mode, protected host, original-data execution,
native interpretation, clinical utility or scientific qualification is supplied.

## Owner interface

An operator first authenticates the predecessor source closure in `SOURCE.json`,
constructs its existing `Cohort` with the independently frozen support, causal
protocol, scales, recipe and budgets, and retains exclusive serialized ownership.
The owner must not mutate requests or Cohort state during a call; this synchronous
adapter supplies no concurrent-mutation protection or multithreaded transport.
Wrap that object with:

```python
delivery = RasterDelivery(cohort, raster_protocol,
                          expected_protocol_sha256=frozen_raster_protocol_sha256)
```

Import `RasterDelivery` from this package's `raster.py` using the deployment's
ordinary source-verification/import route. This adapter does not independently
prove how a caller created a Python object; source authentication and exclusive
ownership are operator prerequisites, not a claimed sandbox.

The exact raster protocol fields are:

| Field | Definition |
| --- | --- |
| `schema` | `neural009_causal_raster_v1` |
| `gutter_px` | Fixed left label/scale gutter, at least 16 pixels |
| `header_px` | Fixed header, at least `40 * font_scale` pixels |
| `footer_px` | Fixed footer, at least `12 * font_scale` pixels |
| `font_scale` | Integer 1 through 4; every glyph is an explicit 5 by 7 bitmap |
| `max_image_pixels` | Positive integer, no more than 4,194,304 |
| `max_png_bytes` | Positive per-image limit, no more than 16 MiB |
| `max_total_png_bytes_per_record` | Positive cumulative successful-image limit, at least the per-image limit |

The commitment uses canonical JSON: sorted keys, separators `(',', ':')`, ASCII
escaping, no nonfinite numbers, encoded as UTF-8, then SHA-256. The constructor
detaches the supplied primitive-valued protocol. Source identity, font, PNG
encoding and rasterization algorithm must also be frozen independently; a protocol
digest does not authenticate the installed code or prove pre-outcome freezing.

`case_ids()`, `start_edf(...)`, `abort_active()` and `finish()` delegate to the
existing owner interface. The active start reply identifies the inactive raster
representation. `dispatch(request)` accepts the unchanged typed `view` and
`answer` requests. It calls the original dispatcher exactly once. Non-view replies
retain their existing form; the adapter never supplies score feedback.

Successful view replies contain exactly `case_id`, `status`, `endpoint_tick`,
`view_id`, `representation`, `image_mime_type`, `image_png`, and `image_sha256`.
`image_png` is a Python byte string containing a PNG, `image_mime_type` is
`image/png`, and `representation` is
`inactive_raster_png_not_native_qualified`. The original opaque view identity is
retained and the image digest commits the delivered byte string. No SVG, waveform
array, source channel index, recording/person join, source filename/hash, scale
map, reference or complete support is returned in these structured fields.

A separate host must deliver the PNG as an actual image attachment with the
authenticated bytes and intended display resolution. A byte string, JSON/base64
description or successful PNG decoder alone does not establish that a participant
received or interpreted a native image. That host must also enforce filesystem,
network, tool/model, secret, cross-case-memory and feedback boundaries. Only the
adapter replies may be delivered in the raster condition; giving participants the
underlying Cohort, its typed SVG route or private Python attributes bypasses this
condition. There is no native provider or transport implementation here.

`finish()` is operator-only. It retains the unchanged candidate and complete
record ledger, adding private raster-protocol and per-record PNG-byte accounting.
The existing scorer can consume its unchanged `candidate` only when the original
complete-support checks succeed. All incompleteness and failure remain visible.

## Visible geometry and clock

The source trace width and channel-band height are retained without shrinking.
The original band height must be at least `32 * font_scale`. PNG width is
`gutter_px + trace_width + 8`; height is
`header_px + number_of_channels * band_height + footer_px`. The background is
white. Channels retain selected order, including distinct bands for duplicate
labels. Labels preserve exact printable ASCII case and punctuation; unsupported
glyphs or text that does not fit the frozen gutter/canvas cause failure. There is
no case conversion, substitution, truncation, wrapping or automatic resizing.

The header has four visible lines at `x=8`, `y=4+9*font_scale*line_number`:

```text
CAUSAL EEG - uV
NATIVE TIME {first_sample}/{rate} TO {last_sample}/{rate} s
DECISION ENDPOINT {active_endpoint}/10 s
ALL SELECTED SAMPLES; NO FILTER
```

Each channel's exact label, `MAX {maximum} uV`, and `MIN {minimum} uV` occupy three
lines in its gutter at `y=band_top+4+9*font_scale*line_number`.
These values are rendered as pixels, not structured signal metadata. The footer
reads `RASTER DISPLAY; NATIVE EXECUTION UNQUALIFIED`. Native sample times remain
distinct from the active decision endpoint: the last displayed native sample may
precede it, including at a recording's last bin. Fractional seconds are displayed
as exact sample-count/rate expressions instead of a rounded decimal clock.

The trace origin is `(gutter_px, header_px)`. The closed parser accepts only the
pinned renderer's `svg`, `title`, `g` and `polyline` structure, exact attributes,
matching channel titles, and expected channel/point counts. Declarations and
processing instructions are refused. Every finite point must lie in its original
channel band, and horizontal positions must match the original sample spacing.
The source's nine-significant-digit coordinate representation is retained. Pixel
locations use Python nearest-integer rounding; every adjacent segment is drawn
with the donor's integer line algorithm. A one-sample trace draws a visible pixel.
Neither amplitude nor line segments are clipped. Out-of-range samples already
fail in the predecessor; out-of-band coordinates fail here.

The component adds no filtering, resampling, lag search, gap filling, cross-record
context or autoscaling. Raster overdraw and finite resolution can conceal distinct
samples: plotting every segment does not make the image lossless. Freeze window
length, pixel/time density, amplitudes and actual display resolution before a
comparison. Readability and native execution remain unqualified, especially for
dense multichannel windows or hosts that rescale an image after delivery.

## Bounds and failure

SVG input is limited to 8 MiB and the predecessor's declared byte limit. The
closed parser permits at most 262,144 points and the predecessor's declared
window/value limits. Total integer line steps are bounded at 16,777,216. Image
pixels and exact stored-PNG size are checked before canvas allocation. These are
source guards, not OS memory isolation or measured full-cohort runtime guarantees.

Construction/protocol refusal consumes no view. Once the predecessor has accepted
a view, a parse, glyph, layout, image-budget or rendering error calls its existing
`_fail('raster_refused')` path. The failed record remains in its ledger, incomplete
cohorts cannot produce candidates, and original cleanup failures retain ownership
and their failure evidence. There is no successful empty-image reply, retry that
erases the failure, hidden record exclusion or SVG fallback. Successful views
consume both original SVG/view budgets and cumulative PNG bytes. Answers do not
consume another view or reveal additional EEG.

## Source and generated controls

The standard-library font/line/PNG primitive is adapted from the exact
NEURAL-077 `visual-viewer-v1/raster.py` identified in `SOURCE.json`. Its fixed
1,400 by 820 canvas, uppercasing behavior, ERP labels and clipping routine are not
reused. The adapted canvas has bounded explicit dimensions and refuses clipping;
lowercase and remaining printable ASCII glyphs are explicit. PNGs contain only
IHDR, IDAT and IEND, RGB8 pixels, filter-zero rows and stored-DEFLATE blocks with
CRC/Adler checksums. No SVG, text chunk, metadata, external font, imaging package
or compressor-version-dependent output is embedded.

The focused `tests/test_raster.py` uses generated signals and metadata to check
calibration/geometry, visible labels and timing, PNG structure, causal exposure,
complete candidate binding and retained failure behavior. Its invented inputs are
not CHB-MIT waveforms or scientific results. Execution receipts belong to the
separate source handoff. No authentic-data reproduction, detector competence,
paired uncertainty, protected execution or clinical timeliness is established.
