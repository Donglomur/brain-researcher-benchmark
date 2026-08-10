# Characterising dynamic functional connectivity (DYNFC-001)

## Scientific context

Resting-state functional connectivity is not static: sliding-window and related methods
suggest that inter-regional coupling **fluctuates over time**, and such "dynamic functional
connectivity" — including recurring connectivity **states** — is widely studied as a feature
of brain organisation (Hutchison et al., 2013, *NeuroImage*,
https://doi.org/10.1016/j.neuroimage.2013.05.079; Allen et al., 2014).

## Task

Using the nilearn-pinned ABIDE derivatives
(`nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_dosenbach160"])`),
compute **time-resolved (sliding-window) functional connectivity** for each subject and
**characterise how connectivity fluctuates over time** — for example, the magnitude of
window-to-window connectivity variability, and/or any recurring connectivity states.

Report, in plain terms, **what you find about the temporal dynamics of resting-state
connectivity on these data**.

## Data

**Dataset:** ABIDE resting-state (Dosenbach-160). It is downloaded programmatically at runtime by the loader used in the Task section — nothing is pre-placed in the container, so **internet access is required** on the first run (the download is cached locally afterwards). Fetch it with:

```python
nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_dosenbach160"])
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `dynamics.json` — a quantitative measure of the **time-resolved connectivity variability**
 (e.g. mean window-to-window standard deviation of edges), the window length, `n_subjects`,
 and any dynamic states you identify.
- `run_metadata.json` — dataset, atlas, number of subjects, window length, and the analytic
 choices you made.
- `findings.md` — a short written summary of what you found about the temporal dynamics of
 connectivity.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `dynamics.json`, and `findings.md`.
