# Decoding binary contrast patterns from early visual cortex (MIYAWAKI-001)

## Scientific context

Miyawaki et al. (2008, *Neuron* 60:915, https://doi.org/10.1016/j.neuron.2008.11.004)
showed that the 10x10 binary contrast image a person is viewing can be decoded, pixel by
pixel, from the multi-voxel pattern of BOLD activity in early visual cortex. The headline
number such analyses report is the **cross-validated decoding accuracy** — how often the
on/off state of a stimulus pixel is recovered correctly out-of-sample.

## Task

Using the Miyawaki 2008 dataset (`nilearn.datasets.fetch_miyawaki2008`), **decode the
presented binary contrast pattern from early-visual-cortex BOLD and report the mean
pixel decoding accuracy** of a linear decoder.

Work with the **random-image runs only** — the 20 functional runs and matching label
files whose names contain `random` (`data_random_run*.nii.gz` and
`data_random_run*_label.csv`). The `figure`-image runs are not used here.

Each label file is a `(n_volumes, 100)` integer table: one row per acquired volume, one
column per pixel of the flattened 10x10 stimulus grid. Entries are `-1` on volumes with
**no stimulus** (rest), and `0`/`1` (pixel off / on) on volumes while a contrast pattern
was displayed.

Pin the analysis as follows so the number is comparable:

- **Features:** the voxels inside the dataset's early-visual-cortex mask (`dataset.mask`),
  extracted with `nilearn`'s `NiftiMasker`. **Standardize (z-score) and detrend each run's
  voxel time series separately** (`standardize="zscore_sample"`, `detrend=True`).
- **Hemodynamic alignment:** the BOLD response lags the stimulus, so pair each stimulus
  pattern with the volume acquired **2 volumes (TRs) later** — i.e. within each run drop
  the first 2 BOLD volumes and the last 2 label rows, so that BOLD volume *t* is matched to
  the label at *t*−2.
- **Samples:** after alignment, keep only the volumes on which a stimulus was present
  (drop the rest volumes, whose label row is all `-1`). Treat the surviving labels as the
  binary `{0,1}` target pattern.
- **Decoder:** a single multi-output **ridge regressor**,
  `sklearn.linear_model.Ridge(alpha=1.0)`, trained to predict all 100 pixel values at
  once; threshold its output at **0.5** to obtain the predicted on/off state of each pixel.
- **Metric:** the **mean pixel decoding accuracy** — the fraction of (pixel, held-out
  sample) predictions that match the true pixel state, averaged over all 100 pixels and all
  held-out samples (chance ≈ 0.5, since the random patterns are ~50% on).

Report the cross-validated mean pixel decoding accuracy of this decoder.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `decoding_results.json` — at least a field `mean_pixel_accuracy` (float in 0–1), the
  cross-validated mean pixel decoding accuracy you obtained, plus `n_samples`, `n_voxels`,
  `n_pixels`, `n_runs`, and `chance`.
- `run_metadata.json` — dataset id, the runs used, mask, and the preprocessing / decoder
  choices you made.
- `findings.md` — a short written summary stating the cross-validated mean pixel decoding
  accuracy and how you evaluated it. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a
non-empty reason, and still write parseable `run_metadata.json`, `decoding_results.json`,
and `findings.md`.
