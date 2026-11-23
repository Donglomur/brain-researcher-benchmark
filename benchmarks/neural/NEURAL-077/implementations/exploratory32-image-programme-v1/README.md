# Frozen four-demonstration image programme

This directory preserves the exact programme evaluated in the [22 November 2026 exploratory ERP image pilot](../../docs/exploratory32-fixed-image-pilot-20261122.md). It is one participant method for an exploratory 32-case experiment within NEURAL-077, not a new benchmark, an established baseline, or a readiness promotion.

`classify.py` is byte-identical to the source frozen before query exposure: **13,848 bytes**, SHA-256 `559d391aab50ff00c1684de248f21b48ca75a9f5bf3a427f1f55f50310d7fc11`. A failure-reporting correction preceded that freeze. This publication makes no algorithm changes and performs no new programme runs.

## Inputs and invocation

The programme uses Python 3, NumPy, and the Python standard library. Exact Python and NumPy versions are not established by the released pilot report; no dependency lock or replacement environment is asserted here. It sets six common numerical-library thread variables to one before importing NumPy.

Supply one query and exactly four demonstration PNG paths. The demonstration order has hard-coded event labels `(0, 1, 0, 1)`, where 0 is standard and 1 is target. Changing the order changes the reference. The trial identifier is copied to output and is not a classification feature. The following paths and identifier are placeholders, not released pilot records:

```sh
python3 classify.py \
  --trial-id example \
  --query /path/to/query.png \
  --demos /path/to/demo-standard-a.png /path/to/demo-target-a.png \
          /path/to/demo-standard-b.png /path/to/demo-target-b.png
```

On success, stdout is one JSON object containing `trial_id` and `target_probability`. The probability is explicitly uncalibrated. Exceptions during feature extraction or classification terminate with a nonzero exit and a diagnostic of the form `classification_failed: ValueError`, with no probability JSON. The handler reports the exception class, not its detailed message. Original failures count incorrect in the pilot; they are not successful predictions or missing observations to discard.

## Frozen behavior

The source reads each PNG directly, validates its checksums and fixed 1,400 × 820 geometry, and supports noninterlaced eight-bit grayscale, RGB, palette, grayscale/alpha, and RGBA encodings. Ancillary PNG metadata are not interpreted. The decoder uses NumPy and standard-library code; it does not call an image service or external process.

Only the two fixed blue-trace crops are used for features. Blue chromaticity separates the traces from grid lines, text, and the red marker. The midpoint of each column's vertical blue extent estimates the trace center. The programme requires blue pixels in at least 97% of columns in each crop, then interpolates gaps, maps coordinates to the fixed display scale, and removes the pre-event rasterization offset. It rejects images failing its geometry, encoding, checksum, coverage, or finite-value requirements. This documents code behavior; it is not a diagnosis of any particular observed failure.

The features comprise two-channel post-event 50-ms bins, broader temporal bands, broad extrema, and baseline RMS. A fixed symmetric distance combines shape, bands, and extrema with weights 0.65, 0.25, and 0.10 and permits a ±50-ms shape shift. The four demonstrations determine a label-blind scale and kernel bandwidth. Equal class reference weights produce an uncalibrated target probability, shrunk toward 0.5 according to support and constrained to [0.1, 0.9]. No parameter is fit to the query. Filenames, trial aliases, and image header/footer text are not classification features.

These fixed geometry and coverage assumptions limit applicability. The original six runtime errors remain part of the reported outcome. The source is preserved without repair; testing a revised extractor or classifier requires a separate prospective experiment. This code does not supply or recreate the private pilot inputs, labels, individual predictions, exact direct-model snapshots, or complete internal tool traces.
