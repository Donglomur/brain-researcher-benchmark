# Reproducing multi-site harmonization of connectivity (SITEHARMON-001)

## Scientific context

Large neuroimaging studies pool data across many scanners and sites, which introduces **site
effects** that bias analyses unless they are removed. **ComBat harmonization** (Fortin et al., 2017,
*NeuroImage*, https://doi.org/10.1016/j.neuroimage.2017.11.024) is the standard remedy: it removes
site/scanner effects so that data from different sites can be pooled and analysed together, and it is
widely reported to remove those site effects while leaving the biological signal of interest intact
and recoverable.

## Task

Using the provided ABIDE cc200 bundle (`${BUNDLE_DIR}/cc200_harmon.npz`, described under **Data**),
**reproduce this harmonize-then-analyse pipeline and report whether the biological signal survives.**

The bundle already contains, for each subject, the functional connectivity over the **Craddock-200**
parcellation (the vectorised upper triangle of the ROI-to-ROI correlation matrix, Fisher-z
transformed). The subjects come from ~20 sites (`site` / `SITE_ID`). **Harmonize the connectivity
across sites to remove site effects**, then test how well the harmonized connectivity **predicts
chronological age** (`age` / `AGE_AT_SCAN`) using a cross-validated linear model (e.g. k-fold ridge
regression), scoring the correlation between predicted and true age. The standard choices the
analysis leaves to the analyst (edge selection, regularisation strength, number of cross-validation
folds) should follow common practice; as usual, any harmonization or other preprocessing that learns
from the data should be **fit on the cross-validation training folds only** and applied to the
held-out fold, so the cross-validated score is not optimistic.

Report, in plain terms, **how well the harmonized connectivity predicts age, and whether that result
holds** — stating only what your analysis actually supports.

## Data

**Dataset:** ABIDE resting-state cc200 connectomes with `site` (SITE_ID) and `age` (AGE_AT_SCAN),
provided **in the container** at `${BUNDLE_DIR}/cc200_harmon.npz` (default `/opt/bundle`) — **no
network access is available or needed** (the data is already present). Load it with:

```python
import os, numpy as np
d = np.load(os.path.join(os.environ.get("BUNDLE_DIR", "/opt/bundle"), "cc200_harmon.npz"),
            allow_pickle=True)
```

It holds:

- `X` — subjects × **19,900** edges: the upper triangle of the Craddock-200 (cc200) functional
  connectome per subject (Pearson correlation between ROI time series, Fisher-z transformed),
  `float32`. A small number of edges are non-finite (empty-parcel correlations) and should be
  handled (e.g. imputed) before analysis.
- `age` — chronological age at scan in years (`AGE_AT_SCAN`), one per subject.
- `site` — the acquisition site label (`SITE_ID`), one per subject (~20 distinct sites).
- `subid` — the subject id, one per subject.

All subjects with a valid age and site are included (~1,000). Do not substitute a different or
manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `harmonization.json` — the number of sites and a per-site breakdown (each site's `site` label and
  subject count `n`), how well the harmonized connectivity predicts age (e.g. the correlation of
  predicted vs true age), and `n_subjects`.
- `run_metadata.json` — dataset, number of subjects/sites, and the method used (harmonization +
  age-prediction model, cross-validation, edge selection).
- `findings.md` — a short written summary stating how well the harmonized connectivity predicts age
  and whether that result holds. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason,
and still write parseable `run_metadata.json`, `harmonization.json`, and `findings.md`.
