# Four-demo fixed-image ERP reference

This is a prospective conventional reference candidate for NEURAL-077. It predicts
the released target-event label using the same four labeled demonstration images
and one fixed query image intended for a direct-interpretation arm. It uses only
Python's standard library. There is no authentic-image execution, performance
measurement, empirical baseline qualification, or improvement claim in this
source contribution.

The earlier [exploratory programme](../exploratory32-image-programme-v1/README.md)
and its measured failures remain unchanged. This candidate is a new method for a
future frozen comparison. It must not replace or rescore that programme on the
old pilot and call the result a prospective improvement.

Development used the public renderer/programme source, prospective study design,
historical aggregate results and the label-free extraction-failure diagnosis.
No authentic demonstration/query image, per-case answer, private label or raw
signal was opened while building this candidate. Its method choices were fixed
without evaluating them on the old or proposed new cases.

## Inputs and required upstream checks

Supply exactly four authorized demonstrations in the order **standard, target,
standard, target**, followed later by one query. No other training images, raw
EEG, class prevalence, identities, labels, or previous predictions are inputs.
Demo labels come from this declared order; filenames, title/footer text and PNG
metadata are not prediction features.

The fixed view is the [original renderer](../visual-viewer-v1/raster.py) at
1400 × 820 pixels, Cz then Pz, gain20 native units/division, the complete
[-250, 750) ms epoch and positive-up display. Both participant arms must receive
identical decoded pixels. The initial renderer's last actual sample is
749.0234375 ms; x=1300 is the exclusive endpoint and is not extracted.

`--profile neural077-initial-cz-pz-gain20-v1` is an **operator assertion**, not an
OCR check. The parser verifies dimensions and PNG format; an image rendered with
the wrong gain, channel order or time window can have identical dimensions.
An external authenticated image manifest must establish the view, authorized
demo identities and order, and query identity before this programme is used.
The model records hashes of its four supplied demos. That record alone does not
prove that the supplied demos were the authorized ones.

Accepted images are opaque, noninterlaced 8-bit RGB PNGs, at most4MiB each.
The canonical renderer and its RGB lossless recoding fit this format. All five
PNG row filters are supported. Palette, grayscale, alpha/transparency, unknown
critical chunks, malformed streams and trailing data are refused. A separately
authorized codec would be required for other formats; do not silently change
pixels or retry failed evaluation cases.

## Frozen method

1. Inside each181-pixel-high trace panel, find blue pixels using fixed color
   thresholds. At each column, take the midpoint of the visible blue extent.
   The feature is a lossy raster ordinate. A steep rasterized line can contain
   many pixels; its midpoint is not an original sampled EEG value.
2. Normalize ordinates by the90-pixel half-height. Subtract that image/channel's
   mean of visible prestimulus columns. If the baseline is entirely absent,
   that channel has no supported poststimulus features.
3. Average visible ordinates in15 postmarker50-ms bins per channel. Missing
   columns are never interpolated, set to zero, or assigned a clipping boundary.
   A fully hidden bin has `null` value and zero support. Visibility fractions are
   retained. Clipping can still bias a visible-only mean or baseline; this
   method does not reconstruct hidden amplitudes or remove that selection bias.
4. Fit two class centroids from the two authorized demos per class. Weight each
   feature by its visible fraction and its demonstration's baseline coverage.
   Normalize each channel by the median of the four demo baseline RMS values,
   floored at one vertical pixel. Query noise or amplitude never refits a scale,
   centroid, threshold or other parameter.
5. Use the same feature weights for both class distances: the minimum of the
   query and two class supports, multiplied by query baseline coverage. Compute
   weighted mean squared standardized distance to each centroid. A dimension
   visible only for one class cannot advantage that class.
6. Turn half the standard-minus-target distance difference into a logistic
   score, with the argument bounded to[-60,60], then shrink it toward0.5 by the
   total common support divided by30. This is an **uncalibrated similarity
   score** in the probability field. Support shrinkage expresses the chosen
   method's reduced confidence; it is not a confidence interval or calibration
   guarantee. Four demos cannot establish an optimized or strong EEG classifier.

Identical centroids and equal distances produce0.5. The existing `p >= 0.5`
decision convention assigns this tie to target. No common supported feature
produces a failure and no probability JSON. Zero variance uses the fixed pixel
floor; no result-driven threshold selection or query-time tuning occurs.

## Fit before query access, then predict

From this implementation directory, with Python3.11 or later:

```sh
python3 -I -S -B reference.py fit \
  --profile neural077-initial-cz-pz-gain20-v1 \
  --demos standard-a.png target-a.png standard-b.png target-b.png \
  --output reference.json

python3 -I -S -B reference.py predict \
  --profile neural077-initial-cz-pz-gain20-v1 \
  --model reference.json --model-sha256 FROZEN_MODEL_SHA256 \
  --query query.png --trial-id OPAQUE_TRIAL_ID
```

The first command creates a new model file without overwriting an existing one
and prints its byte count and SHA256. Freeze that file, programme, runtime and
protocol before any new query access. The model binds the current programme's
source hash and fixed configuration. The second command authenticates the model
before opening the query and emits only `trial_id` and `target_probability` on
success. A failure returns exit2 and stderr; stdout contains no prediction.
The fit output is data-derived runtime material and is not part of this public
source release.

Hash checks establish byte identity under the supplied expected digest. They do
not attest fit provenance, elapsed ordering, authorized inputs or filesystem
isolation. The trusted study operator must enforce those boundaries. This CLI
does not sandbox itself or provide an image-delivery adapter.

## Source checks and remaining evaluation

```sh
python3 -I -S -B test_reference.py --renderer ../visual-viewer-v1/raster.py -v
```

Generated controls cover known offsets, temporal bins, missing/clipped regions,
absent baselines, support symmetry, scale freezing, degenerate demos, marker/text
exclusion, PNG filters/refusals, model admission and separate-process fit/predict.
One control uses the unchanged renderer with a generated +100-native-unit
plateau at gain20: its wholly hidden interior must remain missing. Generated
fixtures establish software behavior, not EEG discrimination or authentic-image
compatibility.

Next, under a separately selected execution protocol, qualify the exact four
authorized demo images without inspecting evaluation queries. Freeze this
method, any other comparators, direct-arm configuration, cohort, failure policy
and primary analysis before fresh query execution. Preserve every case and
first error, count failures in the declared denominators, and use person-level
paired uncertainty. A future640-query proposal is a distinct selected subset,
not the registered full6400 endpoint or unseen-person generalization. Competence
and relative direct-versus-programme performance remain empirical questions.
