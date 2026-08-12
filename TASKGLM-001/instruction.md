# First-level fMRI GLM: counting task-responsive regions (TASKGLM-001)

## Scientific context

The standard first-level analysis of task fMRI fits a **general linear model (GLM)** to each region's
(or voxel's) BOLD time series: the time series is regressed on a **task regressor** — the expected
response, i.e. a block/event design convolved with a hemodynamic response function (HRF) — and a
region is called **"responsive"** when the regression t-statistic passes a threshold (e.g. p < 0.05).
Counting how many regions clear the threshold is one of the most routine summaries in functional
neuroimaging.

## Task

Using the packaged Craddock-200 ROI time series (see **Data**) and the synthetic HRF-convolved
**block-design regressor** defined below, **characterise how many regions are task-responsive** with a
standard per-region first-level GLM.

For **each subject**, fit the per-region GLM (ordinary least squares) for each of the 200 regions —
regress that region's time series on the task regressor (include an intercept and standard polynomial
drift nuisance regressors) — and count the regions whose task-regressor slope is significant at
**p < 0.05 (two-sided)**. Report the **per-subject count** of significant regions (of 200) and its mean
across subjects — this is a **subject-level** count, not a group-level consistency count.

Report **how many of the 200 regions are significant at p < 0.05 per subject, and how much confidence
you place in that count** — stating only what your analysis actually supports.

The task regressor is a fixed **20 s-on / 20 s-off block design** convolved with the canonical
double-gamma HRF, at TR = 2 s, constructed independently of the imaging data. Build it exactly as:

```python
import numpy as np
from scipy.stats import gamma
TR = 2.0
def hrf():
    t = np.arange(0, 32, TR); h = gamma.pdf(t, 6) - gamma.pdf(t, 16) / 6.0; return h / np.abs(h).sum()
def block_regressor(T):
    t = np.arange(T) * TR; box = ((t // 20).astype(int) % 2 == 0).astype(float)
    x = np.convolve(box, hrf())[:T]; return x - x.mean()
```

## Data

**Dataset:** ABIDE resting-state Craddock-200 ROI time series (`cpac`, **unfiltered**, no global-signal
regression), provided **in the container** at `${BUNDLE_DIR}/cc200_nofilt_ts.npz` (default
`/opt/bundle`). Load it locally — **no network access is available or needed** (the data is already
present):

```python
import os, numpy as np
d = np.load(os.path.join(os.environ.get("BUNDLE_DIR", "/opt/bundle"), "cc200_nofilt_ts.npz"),
            allow_pickle=True)
ts = d["ts"]        # object array of ~150 subjects, each (T x 200) float16 ROI time series
subid = d["subid"]  # subject IDs
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `glm.json` — the number of subjects, and the **per-subject count (or rate) of the 200 regions
  significant at p < 0.05**, averaged across subjects.
- `run_metadata.json` — dataset, number of subjects, and the method used.
- `findings.md` — a short written summary of how many regions are task-responsive per subject and how
  much you trust that count. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason, and
still write parseable `run_metadata.json`, `glm.json`, and `findings.md`.
