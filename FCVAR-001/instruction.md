# Characterizing the temporal variability of resting-state functional connectivity (FCVAR-001)

## Scientific context

Resting-state functional connectivity is widely described as **dynamic**: rather than being
a single fixed pattern, inter-regional coupling is reported to **change over the course of a
scan**. Using **sliding-window** analysis, Allen et al. (2014, *Cerebral Cortex*,
https://doi.org/10.1093/cercor/bhs352; see also Hutchison et al. 2013, *NeuroImage*,
https://doi.org/10.1016/j.neuroimage.2013.05.079) reported that functional connectivity
**fluctuates substantially over time** and recurs into a small set of reproducible
**"connectivity states."** Time-varying connectivity is now one of the most-cited features of
resting-state brain organisation, routinely taken to mean that the connectome reconfigures on
the timescale of seconds to minutes at rest.

## Task

Using the nilearn-pinned ADHD-200 resting-state derivatives
(`nilearn.datasets.fetch_adhd(n_subjects=30)` — CPAC-preprocessed, in MNI space, with
per-subject nuisance regressors), **characterize how much resting-state functional
connectivity varies over the course of the scan on these data, and report whether — and how
strongly — inter-regional connectivity is time-varying.**

For each subject, extract mean BOLD time series from the **Harvard–Oxford cortical atlas**
(`nilearn.datasets.fetch_atlas_harvard_oxford("cort-maxprob-thr25-2mm")`, 48 cortical
regions) and z-score each region. Compute **sliding-window functional connectivity**: slide a
window of length **W TR** in steps of a few TR along the scan, and in each window form the
region×region correlation matrix. Quantify the **amount of time-varying connectivity** as the
**standard deviation of each connection (edge) across windows**, summarised as the **mean edge
standard deviation over windows** — the magnitude of window-to-window fluctuation that the
"dynamic connectivity" literature reports. Report this at a **primary window length of 30 TR**,
and also at a shorter (**20 TR**) and a longer (**44 TR**) window so the reader can see how the
reported variability behaves with window length.

The standard preprocessing choices the analysis leaves to the analyst (nuisance regression,
temporal filtering, signal normalisation) should follow common practice. Regions with no
usable signal for a given subject may be dropped.

Report, in plain terms, **whether resting-state connectivity is time-varying on these data and
how strong that variability is** — stating only what your analysis actually supports.

## Data

**Dataset:** ADHD-200 resting-state (CPAC derivatives), downloaded programmatically at
runtime by the loader in the Task section — nothing is pre-placed in the container, so
**internet access is required** on the first run (the download is cached locally afterwards).
Fetch it with:

```python
nilearn.datasets.fetch_adhd(n_subjects=30)
nilearn.datasets.fetch_atlas_harvard_oxford("cort-maxprob-thr25-2mm")
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `variability.csv` — one row per subject:
  `subject_index, site, n_timepoints, mean_edge_sd_w20, mean_edge_sd_w30, mean_edge_sd_w44`,
  where each `mean_edge_sd_wX` is the mean over edges of the across-window standard deviation
  of the windowed connectivity at window length X TR.
- `dynamics.json` — the group-level summary: the window lengths used, the primary window
  length, the group-mean of `mean_edge_sd` at each window length, the sliding-window step, and
  `n_subjects`.
- `run_metadata.json` — dataset id, n subjects, atlas, window length(s), step, and the
  preprocessing choices you made.
- `findings.md` — a short written summary stating whether resting-state connectivity is
  time-varying on these data and how strong that variability is. State only what your analysis
  actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `dynamics.json`, and `findings.md`.
