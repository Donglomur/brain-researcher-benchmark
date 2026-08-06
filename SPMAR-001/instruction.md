# First-level fMRI GLM: counting task-responsive regions (SPMAR-001)

## Scientific context

The standard first-level analysis of fMRI fits a **general linear model (GLM)** to each region's (or
voxel's) BOLD time series: the time series is regressed on a task **regressor** (the expected
response — a block/event design convolved with a hemodynamic response function), and the region is
called "responsive" when the regression t-statistic passes a threshold (e.g. p < 0.05).

## Task

Using the nilearn ABIDE resting-state time series over the Craddock-200 parcellation
(`nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_cc200"])`, unfiltered) and the
synthetic HRF-convolved **block-design regressor** constructed by the loader below, fit the standard
per-region first-level GLM (ordinary least squares) for each of the 200 regions.

Report **how many of the 200 regions are significantly associated with the regressor at p < 0.05
(two-sided), and how much confidence you place in that count** — stating only what your analysis
actually supports.

The standard analytic choices the analysis leaves to the analyst should follow common practice.

## Data

**Dataset:** ABIDE resting-state (Craddock-200 ROI time series), fetched programmatically at runtime
— nothing is pre-placed in the container, so **internet access is required** on the first run (cached
afterwards). Fetch it with:

```python
from nilearn.datasets import fetch_abide_pcp
fetch_abide_pcp(pipeline="cpac", derivatives=["rois_cc200"], band_pass_filtering=False,
                global_signal_regression=False, quality_checked=False)
```

The task regressor is a synthetic block design (≈20 s blocks) convolved with a canonical HRF,
constructed independently of the imaging data. Build it exactly as:

```python
import numpy as np
from scipy.stats import gamma
def hrf(tr=2.0, n=32):
    t = np.arange(0, n*tr, tr); h = gamma.pdf(t, 6) - 0.35*gamma.pdf(t, 16); return h/np.abs(h).sum()
def boxcar_regressor(T, rng, tr=2.0):
    x = np.zeros(T); state=0; i=0
    while i < T:
        blk = int(rng.integers(8, 14))
        if state: x[i:i+blk] = 1
        i += blk; state ^= 1
    xc = np.convolve(x, hrf(tr), mode="full")[:T]; return xc - xc.mean()
# per subject: rng = np.random.default_rng(0) reused across subjects, T = n_timepoints
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `glm.json` — the number of subjects, and the count / rate of regions significant at p<0.05 that
  your analysis supports.
- `run_metadata.json` — dataset, number of subjects, and the method used.
- `findings.md` — a short written summary of how many regions are task-responsive and how confident
  you are. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason,
and still write parseable `run_metadata.json`, `glm.json`, and `findings.md`.
