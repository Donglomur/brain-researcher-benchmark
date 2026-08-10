# Resting-state networks from ICA (ICA-001)

## Scientific context

**Independent component analysis (ICA)** of resting-state fMRI is a standard way to recover
**resting-state networks (RSNs)** — a decomposition of the data into spatially independent
components interpreted as functional networks (Beckmann et al., 2005; Smith et al., 2009,
https://doi.org/10.1073/pnas.0905267106). Identifying the RSNs / components is a common analysis
goal.

## Task

Using the nilearn-pinned ABIDE derivatives
(`nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_dosenbach160"])`),
decompose the group resting-state ROI time series with **ICA** (e.g. `sklearn.decomposition.FastICA`) on the concatenated group data over the **Dosenbach-160** parcellation and **report the
components / networks** you recover.

Report, in plain terms, **the resting-state components / networks you find on these data**.

## Data

**Dataset:** ABIDE resting-state (Dosenbach-160 ROI time series). It is downloaded programmatically
at runtime by the loader in the Task section — nothing is pre-placed in the container, so
**internet access is required** on the first run (the download is cached locally afterwards).
Fetch it with:

```python
nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_dosenbach160"], quality_checked=True)
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `components.json` — the number of components (model order) and a description of the components
 recovered; `n_subjects`.
- `run_metadata.json` — dataset, atlas, number of subjects, and the ICA method / model order used.
- `findings.md` — a short written summary of the components / networks.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason,
and still write parseable `run_metadata.json`, `components.json`, and `findings.md`.
