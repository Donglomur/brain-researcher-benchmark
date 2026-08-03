# Decoding object category from ventral temporal cortex (DECODE-001)

## Scientific context

Haxby et al. (2001, *Science*, https://doi.org/10.1126/science.1063736) showed that the
category of a viewed object is represented in **distributed, overlapping** activity across
**ventral temporal (VT) cortex**, such that the viewed category can be **decoded** from the
VT multivoxel response pattern. Multivariate decoding of category from VT cortex is now a
standard demonstration in the field.

## Task

Using the nilearn-pinned Haxby dataset (`nilearn.datasets.fetch_haxby`, the default single
subject), extract the **ventral-temporal-masked** (`mask_vt`) multivoxel time series and the
per-volume stimulus labels. The experiment presents **eight object categories** — `face`,
`house`, `cat`, `bottle`, `scissors`, `shoe`, `chair`, `scrambledpix` — across **12 runs**
(the `chunks` field); exclude the `rest` volumes.

Train a **linear support-vector classifier** to predict the object category from the VT
pattern, and **report the cross-validated decoding accuracy**: the overall **8-way** accuracy
and the per-category accuracy (plus any pairwise decoding you find informative). State the
chance level. The standard implementation choices the analysis leaves to the analyst (voxel
standardisation, detrending, the SVM regularisation `C`, and how you cross-validate) should
follow common practice.

Report, in plain terms, **how well object category can be decoded from VT cortex on these
data** — stating only what your analysis actually supports.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `decoding_accuracy.json` — the **8-way** cross-validated accuracy, the `per_class_accuracy`
  (one entry per category), the `chance` level, and the number of samples.
- `run_metadata.json` — dataset, subject, mask, number of VT voxels, number of runs, and the
  method details you used (classifier, cross-validation, preprocessing).
- `findings.md` — a short written summary of how well category decodes from VT cortex on these
  data. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `decoding_accuracy.json`, and
`findings.md`.
