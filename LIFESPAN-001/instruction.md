# How does the resting functional connectome change across the adult lifespan? (LIFESPAN-001)

## Scientific context

Resting-state functional MRI lets us describe the **large-scale organization of the functional
connectome** — the pattern of correlated spontaneous activity among cortical regions — and how
that organization differs across people. A long lifespan-neuroimaging literature asks how this
organization changes as the healthy adult brain ages (e.g. Damoiseaux 2017, *NeuroImage*,
https://doi.org/10.1016/j.neuroimage.2017.01.077, for a review). The Enhanced Nathan Kline
Institute–Rockland Sample (NKI) acquired resting-state fMRI across a wide adult age range and is a
standard resource for such lifespan questions (Nooner et al. 2012, *Front. Neurosci.*,
https://doi.org/10.3389/fnins.2012.00152).

## Task

Using the packaged NKI resting-state region time series (see **Data**), **characterise how the
large-scale organization of the resting functional connectome changes across the adult lifespan**,
and report the relationship you find between the connectome's organization and age.

For each subject, form the region×region functional connectome (correlate the region time series),
then summarise the **organization** of that connectome and relate your summary to the subject's age
across the cohort. The standard analytic choices this leaves to the analyst — how the connectome is
summarised, how connection strengths are aggregated, the correlation type used against age — should
follow common practice.

Report, in plain terms, **the relationship between the connectome's organization and age** — its
direction and strength — stating only what your analysis actually supports.

## Data

**Dataset:** NKI Enhanced resting-state fMRI (TR = 645 ms), preprocessed and projected to the
`fsaverage5` cortical surface and parcellated into the **148-region Destrieux atlas**. It is
provided **in the container** at `${BUNDLE_DIR}/nki_surface_roi_timeseries.npz` (default
`/opt/bundle`) — no download, **no network access is available or needed** (the data is already
present). Load it locally with

```python
import os, numpy as np
d = np.load(os.path.join(os.environ.get("BUNDLE_DIR", "/opt/bundle"),
                         "nki_surface_roi_timeseries.npz"), allow_pickle=True)
ts     = d["timeseries"]    # (n_subjects, n_timepoints=895, n_regions=148) float32 region time series
age    = d["age"]           # each subject's age in years (18-78)
sex    = d["sex"]           # each subject's sex ('M'/'F')
region = d["region_name"]   # the 148 region labels (hemisphere + Destrieux name)
tr     = float(d["tr"])     # repetition time in seconds (0.645)
```

A subject's connectome is the 148×148 matrix of correlations between the region time series. Do not
substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `results.json` — the number of subjects, and the **relationship between the connectome's
  organization and age** that your analysis supports (the summary/summaries you related to age, each
  with its correlation with age and significance).
- `run_metadata.json` — dataset, number of subjects, and the method used.
- `findings.md` — a short written summary of how the connectome's organization changes across the
  adult lifespan. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason,
and still write parseable `run_metadata.json`, `results.json`, and `findings.md`.
