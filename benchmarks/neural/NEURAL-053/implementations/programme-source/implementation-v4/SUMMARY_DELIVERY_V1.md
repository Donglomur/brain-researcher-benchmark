# Typed summary delivery extension

`summary_delivery_v1.py` writes the existing numerical feature arm to
`features.npy` and an ordered, hash-bound `features.json` descriptor. The
descriptor gives each column's sensor, statistic, expected source unit and
finite-sample denominator, and preserves the caller's opaque row order.
`project_summary_rows` also exposes the same checked projection in memory.

This addresses a source-specific ambiguity in the current packet. The author
MEG preprocessing applies `mne.baseline.rescale(..., mode='zscore')` over the
prestimulus baseline through time zero, then constructs `EpochsArray` with the
original `epochs.info`. A `mag` channel type therefore does not make the saved
values magnetic-field amplitudes in tesla. Neural means are means of these
baseline z-scores. The ocular source converts detrended x/y pixels to degrees;
the pupil signal remains detrended analog voltage. The latter is not calibrated
pupil area despite a contradictory comment in the author script.

The two inspected author files are pinned at commit
`5e0eccac51eac78b57045f5b90b4f53814f56c32`:

- [MEG preprocessing](https://github.com/ViCCo-Group/THINGS-data/blob/5e0eccac51eac78b57045f5b90b4f53814f56c32/MEG/step1_preprocessing.py), SHA-256 `2c20c84a69327750147e7482a032f6a21464a49009cce357b87e26ad4b2361ab`.
- [Ocular preprocessing](https://github.com/ViCCo-Group/THINGS-data/blob/5e0eccac51eac78b57045f5b90b4f53814f56c32/MEG/eyetracking/step1_eyetracking_preprocess.py), SHA-256 `649a119db0fa36e2e50bdeb202e00d4482b4164a8ac1ee5e312a5cdafb6242c9`.

The exporter performs no conversion, rescaling, fitting, label lookup, row
selection or deletion. It validates float32 means/fractions, requires exact
40-sample neural and 240-sample ocular fraction encodings, and rejects nonzero
means paired with zero availability. An observed zero with nonzero availability
remains distinct from the missing-value sentinel. It exports all four existing
arms with widths 542, 6, 548 and 271, respectively. The availability arm contains
fractions only.

Use `write_typed_summary(output_root, features, arm, sensor_names, row_ids,
budget)` inside trusted packet construction after the existing source and fold
checks. `features` has the already selected, matched `neural` and `ocular`
float32 rows. The function requires the original pinned sensor order and V4
opaque row identifiers; it returns the two ordinary artifact pins. It neither
derives nor replaces the protected source-to-row mapping. The fresh output
directory is not an execution authority, and partial writes following a failure
must not be promoted.

These are source-code unit conventions. Authentic derivative header/calibration
compatibility, including the author CSV export's MNE scaling, still requires
the full input qualification. No authentic MEG/eye arrays, source label rows or
private targets were read for this extension. No source preprocessing was run.
The original cohort, 100 <= t < 300 ms window, endpoints, two program conditions,
controls and all V4 source files remain unchanged. This adds no direct,
viewer or per-query investigation result and no model-performance claim.

The extension is additive and is not silently enrolled in V4's frozen 25-source
production capture. Integration must explicitly bind it and its descriptor to
the approved participant transport before selecting this richer export.

Five generated controls passed through the shared two-slot test pool. They
exercise the actual V4 neural/ocular window selectors, every possible fraction
count, all four arm projections, malformed/missingness cases, independent array
storage and actual array/descriptor serialization with opaque row order. The
export test uses an explicitly invented sensor pin; it is software evidence,
not an authentic-input or scientific qualification.
