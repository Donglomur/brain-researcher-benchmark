# Functional connectivity and age across the ABIDE sample (CC200)

## Scientific context

Resting-state functional connectivity is widely reported to change over development
and across the lifespan. The **ABIDE** (Autism Brain Imaging Data Exchange) initiative
aggregates resting-state fMRI from a large sample spanning childhood to adulthood,
providing the statistical power to characterise how a whole-brain summary of functional
connectivity relates to age. This task uses the ABIDE preprocessed derivatives.

## Task

Using the ABIDE preprocessed resting-state sample, **compute each participant's overall
functional connectivity strength** from the Craddock-200 (CC200) parcellation and
**report how that connectivity strength relates to age** across the sample.

### Data

Fetch the derivatives at runtime with nilearn (no credentials):

```python
from nilearn.datasets import fetch_abide_pcp
abide = fetch_abide_pcp(pipeline="cpac", band_pass_filtering=True,
                        global_signal_regression=False,
                        derivatives=["rois_cc200"], quality_checked=False)
```

`abide["rois_cc200"]` is a list of per-participant region×time arrays (200 CC200 regions);
`abide["phenotypic"]` is a table aligned row-for-row with that list and contains
`AGE_AT_SCAN` (age in years).

### Fixed processing (pin exactly)

- For each participant: drop any CC200 region with zero temporal variance, form the
  region×region **Pearson correlation matrix** across the CC200 time series, and
  **Fisher z-transform** the correlations.
- Define the participant's **overall connectivity strength** as the **mean of the
  upper-triangular (off-diagonal) Fisher-z values**.
- Pair each participant's connectivity strength with their `AGE_AT_SCAN`; drop
  participants with missing age.
- Estimate the relationship between connectivity strength and age across the sample —
  report a **correlation coefficient, its p-value, and n** — and characterise it.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `connectivity.csv` — one row per participant with at least a participant identifier,
  `connectivity` (overall connectivity strength), and `age`.
- `connectivity_age.json` — at minimum
  `{"connectivity_age_r": <float>, "p_value": <float>, "n": <int>, "atlas": "cc200"}`.
- `run_metadata.json` — dataset id, pipeline/derivative, atlas, number of participants,
  the connectivity metric, and the method used to relate connectivity to age.
- `findings.md` — a short write-up reporting how overall functional connectivity relates
  to age in this sample. State only what your analysis supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a
non-empty reason, and still write parseable `run_metadata.json`, `connectivity_age.json`,
and `findings.md`.
