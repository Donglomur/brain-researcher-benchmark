# How does the resting functional connectome change across the adult lifespan? (LIFESPAN-001)

## Scientific context

Resting-state functional MRI lets us describe the **functional connectome** — the pattern of
correlated spontaneous activity among cortical regions — and how it differs across people. A long
lifespan-neuroimaging literature asks how resting functional connectivity changes as the healthy
adult brain ages (e.g. Damoiseaux 2017, *NeuroImage*,
https://doi.org/10.1016/j.neuroimage.2017.01.077, for a review). The Enhanced Nathan Kline
Institute–Rockland Sample (NKI) acquired resting-state fMRI across a wide adult age range and is a
standard resource for such lifespan questions (Nooner et al. 2012, *Front. Neurosci.*,
https://doi.org/10.3389/fnins.2012.00152).

## Task

Using the packaged NKI resting-state region time series (see **Data**), **characterise how resting
functional connectivity changes across the adult lifespan**, and report the relationship you find
between functional connectivity and age.

For each subject, form the region×region functional connectome (Fisher-z correlations of the
region time series), then summarise that connectome and relate your summary to the subject's age
across the cohort. Summarise each subject's connectome in **at least two ways**: (i) its
**overall/global mean connectivity** (the mean of all connectome edges), and (ii) the
**segregation of its large-scale networks** — the normalised difference between mean
within-network and mean between-network connectivity (system segregation; Chan et al. 2014), using
a data-driven (age-blind) network partition of the group-mean connectome. Relate each summary to
age across the cohort.

Report, in plain terms, **how the organization of the resting connectome changes across the adult
lifespan** — whether and how each summary relates to age, its direction and strength — stating
only what your analysis actually supports.

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

- `connectome_summary.csv` — one row per subject: `subject_id, age, global_connectivity,
  within_network_connectivity, between_network_connectivity, system_segregation` (the per-subject
  intermediate the age relationships are computed from).
- `results.json` — the number of subjects, and the relationship with age of **each** connectome
  summary — at minimum the overall/global mean connectivity and the system segregation — each with
  its correlation with age (`pearson_r`) and significance (`p`).
- `run_metadata.json` — dataset, number of subjects, and the method used.
- `findings.md` — a short written summary of how resting functional connectivity changes across the
  adult lifespan. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason,
and still write parseable `run_metadata.json`, `results.json`, and `findings.md`.
