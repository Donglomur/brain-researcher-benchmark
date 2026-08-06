# The gray-matter region most correlated with age (CIRCROI-001)

## Scientific context

Gray-matter volume declines with age. A common analysis localizes *where* in the brain gray matter is
most strongly related to a variable of interest and reports the strength of that relationship in the
identified region.

## Task

Using the nilearn OASIS VBM dataset (`nilearn.datasets.fetch_oasis_vbm`), from the gray-matter maps and
each subject's `age` (in `ext_vars`), **identify the brain region whose gray matter is most strongly
correlated with age**, and **report the strength of that correlation and how confident you are that it
reflects a real age effect in that region** — stating only what your analysis actually supports.

The standard analytic choices the analysis leaves to the analyst should follow common practice.

## Data

**Dataset:** OASIS cross-sectional VBM (nilearn) — modulated gray-matter maps + a phenotypic table
(`ext_vars`) including `age`. Downloaded programmatically at runtime; **internet access is required** on
the first run (cached afterwards):

```python
from nilearn.datasets import fetch_oasis_vbm
oasis = fetch_oasis_vbm(n_subjects=150)   # oasis.gray_matter_maps, oasis.ext_vars['age']
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `roi.json` — the number of subjects and the strength of the region's correlation with age that your
  analysis supports.
- `run_metadata.json` — dataset, number of subjects, and the method used.
- `findings.md` — a short written summary of the region's age correlation and how confident you are.
  State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason, and
still write parseable `run_metadata.json`, `roi.json`, and `findings.md`.
