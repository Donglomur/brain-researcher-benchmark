# Cluster-extent inference on fMRI (EKLUND-001)

## Scientific context

Task-fMRI activation is usually reported after **cluster-extent thresholding**: voxels are thresholded
at a cluster-forming threshold, and then only spatially-contiguous clusters larger than a family-wise
(FWE-corrected) size are declared significant. The standard correction uses a parametric model of the
statistic image's spatial smoothness.

## Task

Using the nilearn ADHD-200 resting-state fMRI (`nilearn.datasets.fetch_adhd`) as the imaging data and
the synthetic block-design task regressor constructed below, run a standard **group-level** analysis
(one-sample t across subjects on each subject's task contrast), apply a cluster-forming threshold of
z > 2.58 (~p < 0.01) and standard **cluster-extent FWE correction**, and report **how many activation
clusters survive correction**.

## Data

**Dataset:** ADHD-200 resting-state fMRI (nilearn `fetch_adhd`), fetched programmatically at runtime —
nothing is pre-placed, so **internet access is required** on the first run (cached afterwards):

```python
from nilearn.datasets import fetch_adhd
adhd = fetch_adhd(n_subjects=12) # 4D resting-state functional images
```

The task regressor is a synthetic block design (≈20 s blocks) convolved with a canonical HRF,
constructed independently of the imaging data:

```python
import numpy as np
from scipy.stats import gamma
def hrf(tr=2.0, n=32):
 t = np.arange(0, n*tr, tr); h = gamma.pdf(t, 6) - 0.35*gamma.pdf(t, 16); return h/np.abs(h).sum()
def boxcar(T, rng, tr=2.0):
 x = np.zeros(T); i=0; s=0
 while i < T:
 b = int(rng.integers(8,14))
 if s: x[i:i+b] = 1
 i += b; s ^= 1
 xc = np.convolve(x, hrf(tr), mode="full")[:T]; return xc - xc.mean()
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `cluster.json` — the number of subjects and the cluster-extent result (e.g. surviving cluster count
 / cluster-size threshold / false-positive rate) your analysis supports.
- `run_metadata.json` — dataset, number of subjects, and the method used.
- `findings.md` — a short written summary of how many clusters are significant.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason,
and still write parseable `run_metadata.json`, `cluster.json`, and `findings.md`.
