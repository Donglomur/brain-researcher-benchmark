# Reproducing the "dynamic functional connectivity" result (DYNFC-001)

## Scientific context

Resting-state functional connectivity is not static. Using **sliding-window** analysis,
Allen et al. (2014, *Cerebral Cortex*, https://doi.org/10.1093/cercor/bhs352; see also
Hutchison et al., 2013, *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2013.05.079)
reported that inter-regional coupling **fluctuates substantially over time** and recurs into
a small set of reproducible **"dynamic connectivity states."** This time-varying connectivity
is one of the most-cited features of resting-state brain organisation, widely taken as
evidence that the connectome reconfigures dynamically at rest.

## Task

Using the nilearn-pinned ABIDE derivatives
(`nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_dosenbach160"], quality_checked=True)`,
the first ~60 usable subjects), **reproduce this dynamic-connectivity result and report
whether it holds on these data.**

For each subject, take the mean BOLD time series over the **Dosenbach-160** ROIs and z-score
each ROI. Compute **sliding-window functional connectivity**: slide a **30-TR** window in steps
of **4 TR**, and in each window form the ROI×ROI correlation matrix. Quantify the *amount of
time-varying connectivity* as the **standard deviation of each edge across windows**, summarised
as the **mean edge standard deviation over windows** — the magnitude of window-to-window
fluctuation that the "dynamic connectivity" literature reports. Report this at the **30-TR** window, and also at **22-TR** and **44-TR** windows.

The standard preprocessing choices the analysis leaves to the analyst (nuisance regression,
temporal filtering, signal normalisation) should follow common practice.

Report, in plain terms, **whether the dynamic-connectivity result reproduces on these data** —
stating only what your analysis actually supports.

## Data

**Dataset:** ABIDE resting-state (Dosenbach-160 ROI time series). It is downloaded
programmatically at runtime by the loader in the Task section — nothing is pre-placed in the
container, so **internet access is required** on the first run (the download is cached locally
afterwards). Fetch it with:

```python
nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_dosenbach160"], quality_checked=True)
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `dynamics.json` — the sliding-window connectivity variability (the **mean edge standard
  deviation across windows**) at each window length (**22, 30, 44 TR**), the primary window
  length, and `n_subjects`.
- `run_metadata.json` — dataset, atlas, number of subjects, window length(s), step, and the
  preprocessing choices you made.
- `findings.md` — a short written summary stating whether the dynamic-connectivity result
  reproduces on these data. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `dynamics.json`, and `findings.md`.
