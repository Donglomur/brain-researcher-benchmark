# Reproducing multi-site harmonization of connectivity (HARMON-001)

## Scientific context

Large neuroimaging studies pool data across many scanners and sites, which introduces **site
effects** that bias analyses unless they are removed. **ComBat harmonization** (Fortin et al., 2017,
*NeuroImage*, https://doi.org/10.1016/j.neuroimage.2017.11.024) is the standard remedy: it removes
site/scanner effects so that data from different sites can be pooled and analysed together, and it is
widely reported to remove those site effects while leaving the biological signal of interest intact
and recoverable.

## Task

Using the nilearn-pinned ABIDE derivatives
(`nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_cc200"])`), **reproduce this
harmonize-then-analyse pipeline and report whether the biological signal survives.**

For each subject, form the functional connectivity over the **Craddock-200** parcellation
(vectorised upper-triangle Pearson correlations between the ROI time series). The subjects come from
~20 sites (`SITE_ID` in the phenotypic table). **Harmonize the connectivity across sites to remove
site effects**, then test how well the harmonized connectivity **predicts chronological age**
(`AGE_AT_SCAN`) using a cross-validated linear model (e.g. k-fold ridge regression), scoring the
correlation between predicted and true age. The standard choices the analysis leaves to the analyst
(edge selection, regularisation strength, number of cross-validation folds) should follow common
practice.

Report, in plain terms, **how well the harmonized connectivity predicts age, and whether that result
holds** — stating only what your analysis actually supports.

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
- `findings.md` — a short written summary stating how well the harmonized connectivity predicts age
  and whether that result holds. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason,
and still write parseable `run_metadata.json`, `harmonization.json`, and `findings.md`.
