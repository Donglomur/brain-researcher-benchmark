# Reproducing the ICA resting-state networks (ICA-001)

## Scientific context

**Independent component analysis (ICA)** of resting-state fMRI is a standard way to recover
**resting-state networks (RSNs)** — the data are decomposed into a set of spatially independent
components interpreted as the brain's major functional networks. Beckmann et al. (2005) and
Smith et al. (2009, *PNAS*, https://doi.org/10.1073/pnas.0905267106) reported that ICA of
resting fMRI recovers a canonical set of RSNs (default-mode, visual, sensorimotor,
fronto-parietal, and so on), a decomposition that has become one of the most-reported summaries
of resting-state brain organisation.

## Task

Using the nilearn-pinned ABIDE derivatives
(`nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_dosenbach160"], quality_checked=True)`,
the control subjects), **reproduce this ICA resting-state-network decomposition and report
whether it holds on these data.**

For each subject, z-score each ROI time series over the **Dosenbach-160** parcellation, then
**concatenate the subjects' time series** into a single group data matrix and decompose it with
**ICA** (e.g. `sklearn.decomposition.FastICA`) at a **model order** (number of components)
chosen following common practice (a common choice is ~20). Report the **components / networks**
you recover. Standard implementation choices the method leaves to the analyst (the number of
components, temporal filtering, signal normalisation, sign handling) should follow common
practice.

Report, in plain terms, **the resting-state components / networks you find and whether the RSN
result holds on these data** — stating only what your analysis actually supports.

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

- `components.json` — the number of components (model order) and a description of the components
  recovered; `n_subjects`.
- `run_metadata.json` — dataset, atlas, number of subjects, and the ICA method / model order used.
- `findings.md` — a short written summary of the components / networks and whether the RSN result
  holds on these data. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `components.json`, and `findings.md`.
