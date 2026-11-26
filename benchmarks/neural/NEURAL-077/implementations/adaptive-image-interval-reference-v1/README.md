# Adaptive image interval reference

This is a separately frozen, four-demonstration reference for the existing
`erp-full32-first-unclipped-gain-observation-v1` observation condition. It consumes
only audited rendered images and the observer's permitted action, display and
loss metadata. It supplies source capability for collecting all 6,400 first
predictions and admitting them before the existing target-last endpoint. No
new authentic capture, reference measurement, participant/model run, transport,
sandbox or scientific qualification is established here.

The existing observer is unchanged: gains **20, 50, 100, 200, 500, 1000**, the
first image whose two rendered clipping warnings are absent, and retention of
`cap_clipped` at the terminal gain. All attempted images, actions and metadata
remain in the capture and their complete projection is committed in each
response. The reference uses only the selected image for features; earlier
attempts are retained for provenance. The same policy applies to four demos
and every query. There are no alternate methods, seed selection or tuning
parameters and no query-target interface.

## Fixed method

`reference.CONFIG` defines `erp-adaptive-image-interval-reference-v1`; it was
selected before generated query controls and before any new authentic query
inspection. Fit uses exactly the four protocol-ordered demonstration labels
`[0, 1, 0, 1]`, with two examples per class. Labels mean experimental target
versus standard events; they are not physiological P3 annotations.

1. Decode the authenticated RGB PNG through the existing transport codec. At
   every column x=180..1299 in each channel panel, find the vertical extent of
   pixels exactly equal to the renderer's blue `(20,75,170)`. For panel midpoint
   `m`, blue rows `y_min..y_max`, and selected gain `g`, retain the native-unit
   interval `[(m-y_max-0.5)*g/30, (m-y_min+0.5)*g/30]`. No blue pixels means
   `None`. The half-pixel padding represents display resolution, not a
   statistical confidence interval.
2. Freeze the four demo interval arrays, their complete observation provenance,
   and two channel scales. A scale is the median visible pre-marker RMS of
   demo interval midpoints, floored at `max(demo_gain)/30` (one pixel at the
   coarsest demo gain). There is no fit beyond these four demos.
3. For each query, restrict each channel to columns visible in **all four demos
   and the query**. Use those same pre-marker columns x=180..459 for each
   record's baseline interval mean. The fifteen post-marker bins are 56 pixels
   each, x=460..1299, corresponding to nominal 50 ms display bins. Use identical
   common columns within each bin for all records, subtracting interval means
   with endpoint interval arithmetic. If the common baseline or bin is empty,
   that feature is missing; no interpolation, fill or waveform reconstruction
   occurs. This conservative intersection may discard otherwise visible data.
4. For each class, average endpoints of its two demonstration intervals. Its
   feature distance is the nonnegative gap between query and centroid intervals,
   divided by the fixed demo channel scale, then squared. Weight each bin by
   `(common_bin_columns/56)*(common_baseline_columns/280)`. Average each class's
   distance using exactly these same weights.
5. Let `s=sum(weights)/30`, `d0,d1` be those distances, and
   `z=clip((d0-d1)/2,-60,60)`. Return `0.5+s*(sigmoid(z)-0.5)`. No common support
   yields exactly **0.5**, with an explicit diagnostic, and remains in the
   denominator. These are finite reference probabilities, **not empirically
   calibrated probabilities**.

Changing shared support for a query is the fixed distance rule, not a refit:
no demo array, label, channel scale or configuration changes after model freeze.
Neither other queries nor query labels influence a prediction.

## What the intervals and bounds mean

Pixels per division remain 30. Native units per vertical pixel are `g/30`;
the renderer's in-range sample-placement rounding bound is `g/60`. For a flat
interior trace with amplitude v, the raster midpoint is
`round(v/g*30)*g/30`, giving error at most `g/60`; two such renderings differ by
at most `(g1+g2)/60`. The generated controls also check interval-baselined flat
plateaus away from transitions, where the midpoint-difference bound is `g/30`.

Those bounds do **not** establish recovery of an original EEG sample from a
column. The renderer rounds horizontal positions, draws adjacent segments and
omits portions beyond the display. Sloped, discontinuous or clipped traces can
occupy a vertical span, and missing columns remain unobserved. A column hull is
a feature of that visible raster geometry. Its half-pixel padding is not a
universal inverse-rendering error bound. Larger gains reduce clipping but lose
vertical resolution, and broad intervals can make both distances zero. Native
stored amplitude units remain uncalibrated; no known-microvolt or physical
display-delay claim is added.

## Collection and target-last integration

`runner.py` authenticates `SOURCE_BINDINGS.json`, its own source, and the existing
observer/evaluator/ordering sources before use. It reuses the observer's pinned
viewer/raster/codec/consumer/actions dependency closure. Source loading, image
reads and outputs are charged to explicit read/write/deadline envelopes.
These are cooperative application limits, not OS isolation or a full process
memory controller.

A caller must already hold an authorized complete observation capture and its
trusted `COMPLETE.json` byte/SHA256 descriptor. Collection validates its original
manifest, four demos, sorted 6,400-query roster and exact directory inventory.
It writes reference intent, audits all demo projections, then persists
`MODEL.json` **before opening any query record/image**. Every query gets one
exclusive `RESPONSE-NNNN.json`, including gain, all attempted projection fields,
common support, interval widths and zero-support diagnostics. No target is read.
`predictions.jsonl` uses the existing exact `{trial_id,target_probability}` schema.
Only all 6,400 accepted first outputs yield `COMPLETE.json`; errors retain prior
outputs and `FAILED.json`, and there is no automatic retry/subset path.

`admit` validates complete first-output custody and provenance, source/model
identity, finite nonboolean probabilities, resolution and support diagnostics.
`evaluate_complete` calls the unchanged
`full32-image-uncertainty-v1/adapter.py::ordered_metrics`, which performs complete
public admission before invoking the operator's private-loader callback, then
uses the unchanged `full32-paired-benchmark-v1/evaluator.py::metric_rows` endpoint.
That loader must use the existing `load_private_people` with the original
approved private commitment. This is a new single-reference condition, not an
arm accepted by the old numeric paired-provider receipt format. Expected pins
come from a trusted operator; hashes alone do not establish truthful capture or
participant isolation. The CLI performs unscored collection only.

A future authorized collection would supply explicit caps rather than defaults:

```sh
python -I -S -B runner.py --repository-root /absolute/repository \
  --capture /absolute/committed-observation --capture-bytes BYTES \
  --capture-sha256 SHA256 --output /absolute/fresh-reference \
  --read-bytes ALLOCATED_READS --write-bytes ALLOCATED_WRITES \
  --work-seconds ALLOCATED_SECONDS
```

This is not an execution request or resource allocation. First select and quote
an authentic label-blind byte/visibility census, preserving the original gain
policy. No practical complete-capture time/artifact quote has been established;
the older loose 151.368 GiB ceiling is not a grant. The earlier observer control
suite's 269.8 MiB excursion against its then-256 MiB plan remains historical.
These new generated controls use a prospective 384 MiB declaration and the
shared supervised pool; measured per-job peak RSS is reported separately.

## Generated verification and limits

There are **16 unique controls**: 11 geometry/admission/source-budget controls
and 5 collection/endpoint controls. Rendered tests use the actual existing
renderer, codec and observer; flat/plateau bounds across all six gains,
first-unclipped selection and all-missing cap retention are exercised. Analytic
interval controls check equal support, demo-only fitting, finite probabilities,
resolution ambiguity and missing baselines. Full6,400 collection controls use
explicit generated extraction/scoring substitutes to test orchestration and
first-output custody, not authentic rendering throughput or predictive accuracy.
The target-last control's synthetic labels test ordering/endpoint compatibility
only and are never fit inputs. See `VALIDATION.json` for the preserved initial
test-callback failure and the targeted successful rerun; unchanged passing
controls were not repeated.

```sh
python -I -S -B test_reference.py --repository-root /absolute/repository \
  --scratch-root /absolute/fresh-generated-scratch
```

The fixed-gain20 four-demo references, completed fixed-view results and historical
32-episode actual-model pilot remain unchanged. Adaptive intermediate images and
gain metadata are additional permitted information, so the condition is distinct.
The full32 cohort has prior pilot/reference/aggregate exposure: any future result
on it is development characterization, not independent held-out generalization.
There is no empirical gain, superiority, native-understanding or AI competence
claim. Source acceptance does not require better scores.
