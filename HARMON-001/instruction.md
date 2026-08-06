# Multi-site harmonization of connectivity (HARMON-001)

## Scientific context

Large neuroimaging studies pool data from many scanners/sites, which introduces **site effects**
that must be removed before analysis. **Harmonization** (e.g. ComBat; Fortin et al., 2017,
*NeuroImage*, https://doi.org/10.1016/j.neuroimage.2017.11.024) removes these site effects so that
data from different sites can be analysed together.

## Task

Using the nilearn-pinned ABIDE derivatives
(`nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_cc200"])`), form each
subject's functional connectivity over the **Craddock-200** parcellation. The data come from ~20
sites (`SITE_ID` in the phenotypic table).

**Harmonize the connectivity across sites to remove site effects**, and then test how well the
(harmonized) connectivity **predicts chronological age** (`AGE_AT_SCAN`) — report the accuracy of
age prediction on the harmonized data.

The standard analytic choices the analysis leaves to the analyst (the harmonization method, the
predictor, the cross-validation) should follow common practice.

Report, in plain terms, **how well connectivity predicts age after harmonizing across sites** —
stating only what your analysis actually supports.

## Data

**Dataset:** ABIDE resting-state (Craddock-200 ROI time series) with `SITE_ID` and `AGE_AT_SCAN` in
the phenotypic table. It is downloaded programmatically at runtime by the loader in the Task section
— nothing is pre-placed in the container, so **internet access is required** on the first run (the
download is cached locally afterwards). Fetch it with:

```python
nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_cc200"])
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `harmonization.json` — the number of sites, and how well connectivity predicts age (e.g. the
  correlation of predicted vs true age) after harmonization; `n_subjects`.
- `run_metadata.json` — dataset, number of subjects/sites, and the method used.
- `findings.md` — a short written summary of how well the harmonized connectivity predicts age and
  how confident you are. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason,
and still write parseable `run_metadata.json`, `harmonization.json`, and `findings.md`.
