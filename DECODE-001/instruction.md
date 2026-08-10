# Reproducing Haxby's ventral-temporal object-category decoding (DECODE-001)

## Scientific context

Haxby et al. (2001, *Science*, https://doi.org/10.1126/science.1063736) showed that the category of
a viewed object is represented in **distributed, overlapping** activity across **ventral temporal
(VT) cortex**, such that the viewed category can be **decoded** from the VT multivoxel response
pattern well above chance. Multivariate decoding of object category from VT cortex is now one of
the most-cited demonstrations in the field and the standard benchmark for MVPA.

## Task

Using the nilearn-pinned Haxby dataset (`nilearn.datasets.fetch_haxby`, the default single
subject), **reproduce this decoding result and report whether it holds on these data.**

Extract the **ventral-temporal-masked** (`mask_vt`) multivoxel time series and the per-volume
stimulus labels. The experiment presents **eight object categories** — `face`, `house`, `cat`,
`bottle`, `scissors`, `shoe`, `chair`, `scrambledpix`; exclude the `rest` volumes. Train a **linear
support-vector classifier** to predict the object category from the VT pattern, and **report the
cross-validated decoding accuracy**: the overall **8-way** accuracy and the per-category accuracy,
and state the **chance** level (1/8 = 0.125). Report any pairwise decoding you find informative.

The standard preprocessing choices the analysis leaves to the analyst (masking, detrending, signal
normalisation) should follow common practice.

Report, in plain terms, **whether Haxby's VT object-decoding result reproduces on these data and
how well object category can be decoded from VT cortex** — stating only what your analysis actually
supports.

## Data

**Dataset:** Haxby object-vision task fMRI. It is downloaded programmatically at runtime by the
loader in the Task section — nothing is pre-placed in the container, so **internet access is
required** on the first run (the download is cached locally afterwards). Fetch it with:

```python
nilearn.datasets.fetch_haxby()
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `decoding_accuracy.json` — the **8-way** cross-validated accuracy, the `per_class_accuracy`
 (one entry per category), the `chance` level, and the number of samples.
- `run_metadata.json` — dataset, subject, mask, number of VT voxels, and the method details you
 used (classifier, cross-validation, preprocessing).
- `findings.md` — a short written summary stating whether the decoding result reproduces and how
 well category decodes from VT cortex on these data. State only what your analysis actually
 supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason,
and still write parseable `run_metadata.json`, `decoding_accuracy.json`, and `findings.md`.
