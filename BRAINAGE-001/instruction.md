# The brain-age gap (BRAINAGE-001)

## Scientific context

**Brain age** is a widely used imaging biomarker: a model is trained to predict chronological age
from brain structure, and the **brain-age gap** (predicted − chronological age) is interpreted as
a marker of accelerated or decelerated brain ageing (Franke et al., 2010, *NeuroImage*,
https://doi.org/10.1016/j.neuroimage.2010.01.005). A positive gap ("older-looking brain") is often
related to disease, cognition, or risk factors.

## Task

Using the nilearn-pinned **OASIS VBM** dataset (`nilearn.datasets.fetch_oasis_vbm`, which ships
`gray_matter_maps` and an `ext_vars` table with `age` and clinical `cdr`), train a model to
**predict chronological age** from the gray-matter maps (cross-validated), and compute each
subject's **brain-age gap** (predicted − chronological age).

Then **report what the brain-age gap is associated with** on these data — in particular its
relationship to **chronological age**, and whether it **differs between dementia (CDR > 0) and
healthy (CDR = 0)** subjects.

The standard analytic choices the analysis leaves to the analyst (the model, the smoothing/
resolution, the cross-validation) should follow common practice.

Report, in plain terms, **what the brain-age gap tells you on these data** — stating only what
your analysis actually supports.

## Data

**Dataset:** OASIS-1 VBM gray-matter maps + `ext_vars` (age, cdr, mmse, ...). It is downloaded
programmatically at runtime by the loader in the Task section — nothing is pre-placed in the
container, so **internet access is required** on the first run (the download is cached locally
afterwards). Fetch it with:

```python
nilearn.datasets.fetch_oasis_vbm(n_subjects=403)
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `brain_age.json` — the model performance (e.g. MAE, correlation of predicted vs true age), the
  relationship of the brain-age gap to chronological age, and the dementia-vs-healthy comparison;
  `n_subjects`.
- `run_metadata.json` — dataset, number of subjects, and the method used.
- `findings.md` — a short written summary of what the brain-age gap is associated with and how
  confident you are. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason,
and still write parseable `run_metadata.json`, `brain_age.json`, and `findings.md`.
