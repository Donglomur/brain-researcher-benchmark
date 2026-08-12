# Reproducing the brain-age gap biomarker (BRAINAGE-001)

## Scientific context

**Brain age** is one of the most widely used imaging biomarkers. A model is trained to predict
chronological age from brain structure, and the **brain-age gap** (predicted − chronological age) is
interpreted as a marker of accelerated or decelerated brain ageing (Franke et al., 2010, *NeuroImage*,
https://doi.org/10.1016/j.neuroimage.2010.01.005, "BrainAGE"). A positive gap ("older-looking brain")
is routinely related to disease, cognition, and risk factors, and a larger gap in a clinical group
than in healthy controls is taken as evidence of accelerated ageing in that group.

## Task

Using the nilearn-pinned **OASIS VBM** dataset (`nilearn.datasets.fetch_oasis_vbm`, which ships
`gray_matter_maps` and an `ext_vars` table with `age` and clinical `cdr`), **reproduce this
brain-age-gap biomarker and report whether it holds on these data.**

Fit a **cross-validated** model that predicts **chronological age** from the gray-matter maps (mask the
maps to gray matter, e.g. `NiftiMasker` with a gray-matter template; a regularised linear regressor such
as cross-validated Ridge with k-fold cross-validation is standard), and record its accuracy (MAE and the
correlation between predicted and true age). Compute each subject's **brain-age gap** = predicted −
chronological age. Then use the gap as a biomarker: compare it between **dementia (CDR > 0)** and
**healthy (CDR = 0)** subjects, testing whether the dementia group shows the larger gap that the
accelerated-ageing account predicts.

The standard preprocessing/analytic choices the analysis leaves to the analyst (voxel resolution,
masking, low-variance-voxel handling, the regressor and its regularisation, the number of folds) should
follow common practice.

Report, in plain terms, **whether the brain-age gap behaves as a valid biomarker on these data** —
stating only what your analysis actually supports.

## Data

**Dataset:** OASIS-1 VBM gray-matter maps + `ext_vars` (age, cdr, mmse, ...). It is downloaded
programmatically at runtime by the loader in the Task section — nothing is pre-placed in the container,
so **internet access is required** on the first run (the download is cached locally afterwards). Fetch
it with:

```python
nilearn.datasets.fetch_oasis_vbm(n_subjects=403)
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `subject_gaps.csv` — one row per subject: `age`, `cdr` (blank where not assessed), `group`,
  `predicted_age`, and the brain-age gap(s) you computed.
- `brain_age.json` — the model performance (e.g. MAE, correlation of predicted vs true age), the
  dementia-vs-healthy gap comparison, and `n_subjects`.
- `run_metadata.json` — dataset, number of subjects, and the method used.
- `findings.md` — a short written summary of whether the brain-age gap behaves as a valid biomarker on
  these data. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason, and
still write parseable `run_metadata.json`, `brain_age.json`, and `findings.md`.
