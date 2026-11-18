# Typed waveform presentation for NEURAL-084

This component supplies a missing waveform presentation and response-collection
API for the existing overt-gaze SSVEP task. It is **source construction only**.
It does not change the task, authenticate OpenBMI recordings, execute a model,
qualify a native/no-tools condition, or promote benchmark readiness.

The older `sequential-view-v2` programme manages fit/query filesystem custody;
its use of “view” does not provide a visual EEG viewer. This component is
additive. It reuses that programme's exact fold, training-support and prediction
validators and the preserved public protocol, with their source hashes checked
before loading. The full-cohort scorer remains unchanged.

## Operator interface

Construct `FoldViewer(fold, training, training_epoch, query_epoch)` in a trusted
operator process. `fold` and `training` are the existing validated metadata
objects. Provider callables return one Python list/tuple of 10 by 400 finite
amplitudes, in the exact row order of their already-authenticated source
packets. A NumPy float32 epoch can be converted by the operator using `tolist`;
this module does not load arrays. Providers, source arrays, evaluator code and
private labels must never be accessible to an image-only participant.

For a source mirror, the trusted operator may supply `source_root` pointing to
the task's implementations directory. Only the three exact pinned source
dependencies can load. This is not a participant-selectable path.

`handle` accepts strict UTF-8 JSON bytes (maximum 4096 bytes) and returns a
canonical JSON response. The serial protocol is:

1. `{"action":"information"}` returns the existing public frequency/class
   dictionary, channels, time grid and presentation limits.
2. `{"action":"training","index":0,"channels":["P7","Oz"],"start":0,"stop":400}`
   presents a donor waveform with its already-public ID, label, person, session
   and phase. Every one of 21,200 rows is addressable; calibration inspection is
   optional. There are at most 128 successful views per donor epoch.
3. `{"action":"begin_queries"}` irreversibly retires the training metadata and
   provider from this object and returns the first opaque query ID. This is
   an API lifecycle, not proof that an external process erased all copies.
4. `{"action":"view","id":"<current opaque ID>","channels":["Oz"],"start":0,"stop":400}`
   presents only the current query. Each of 400 queries permits up to 128
   successful waveform views. A query snapshot stays unchanged across views.
5. `{"action":"answer","id":"<current opaque ID>","scores":[0,1,0,0]}`
   irrevocably records four raw scores and advances to the next query. Scores
   are not interpreted as probabilities. All-zero ties remain permissible.
   An answer may be submitted without inspecting a waveform.
6. `{"action":"finish"}` returns an ordinary `neural084_scores_v1` submission
   only after all 400 first-final answers. The existing prediction validator
   checks the result; the viewer never reads gold or computes accuracy.

Unknown fields/actions, duplicate JSON keys, incorrect/future/stale identities,
out-of-range windows, extra channels, booleans and nonfinite scores fail. No
request accepts code, arbitrary paths, filters, transforms, a decoder or target
feedback. Invalid requests do not consume the successful-view budget; a
deployment must separately bound request count, wall time and process lifetime.

## Representation and scientific scope

The source convention remains ten channels P7, P3, Pz, P4, P8, PO9, PO10, O1,
Oz, O2 and all 400 block-mean samples, centered at `0.0045 + 0.01*k` seconds.
The original prospective extraction is unchanged. A view has at least two
adjacent source samples and at most all 400; every channel/sample is available.
There is no filtering, demeaning, rereferencing, frequency extraction, sample
interpolation or decimation. Polylines connect the observed sample centers.

All traces share one symmetric vertical bound from the maximum absolute
amplitude across the complete epoch, irrespective of the requested crop or
channels. The bound is displayed; zero epochs use a display bound of one.
Relative channel amplitude and DC offsets are preserved within the finite
precision of SVG coordinates. Physical units remain explicitly **unverified**;
the renderer does not invent microvolt calibration. Window/channel selection
changes presentation only and supplies no new physiological measurement.

Responses contain SVG text. SVG is a vector observation whose coordinates can
be inspected numerically; **it is not an image-only or no-tools transport**.
A future qualified visual condition must render it to an image on the operator
side, freeze that rendering, enforce participant isolation and record actual
image delivery. Readability, amplitude dynamic range and model performance
require authentic and human/model evaluation; generated tests do not establish
them. The programme still receives numerical arrays, so no equality of visual
and numerical precision is asserted.

This one-fold API does not provide the outer 54-fold executor, a participant
provider, cross-fold state reset or a runtime resource measurement. Those
remain necessary, alongside authenticated 108-recording preparation and
protected gold, before any full benchmark result. The full cohort, four-class
target order, equal-person/session/phase/class score and existing CCA/constant/
frequency-permutation comparisons are unchanged. Overt gaze, stimulus frequency
and location remain coupled; performance cannot isolate covert attention or a
unique neural mechanism.

## Focused controls

`test_viewer.py` uses generated metadata for the complete 21,200-donor/400-query
fold and synthetic integer arrays only. It checks exact sample geometry, crop
scale consistency, training retirement, all400 response compatibility, stale
answers, malformed requests, future-query rejection, invalid scores/epochs,
provider mutation, complete-support validation, per-epoch budgets, zero traces
and the final held-person boundary. These are software controls, not EEG
results. Run with `python -I -B test_viewer.py` after integration. A private
source mirror may set `NEURAL084_SOURCE_IMPLEMENTATIONS` for the test's trusted
dependency location; the public source hashes still must match.
