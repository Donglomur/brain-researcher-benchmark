# Reproducing the ICA resting-state networks (RESTNETS-001)

## Scientific context

**Independent component analysis (ICA)** of resting-state fMRI is a standard way to recover
**resting-state networks (RSNs)** — the data are decomposed into a set of spatially independent
components interpreted as the brain's major functional networks. Beckmann et al. (2005) and
Smith et al. (2009, *PNAS*, https://doi.org/10.1073/pnas.0905267106) reported that ICA of
resting fMRI recovers a canonical set of RSNs (default-mode, visual, sensorimotor,
fronto-parietal, and so on), a decomposition that has become one of the most-reported summaries
of resting-state brain organisation.

## Task

Using the provided ABIDE resting-state bundle (`data/dos160_ica.npz`: per-subject
**Dosenbach-160** ROI time series for the control subjects), **reproduce this ICA
resting-state-network decomposition and report the components you recover.**

For each subject, z-score each ROI time series, then **concatenate the subjects' time series**
into a single group data matrix and decompose it with **ICA** (e.g.
`sklearn.decomposition.FastICA`) at a **model order** (number of components) chosen following
common practice (a common choice is ~20). **Report the components / networks you recover — the
component spatial maps / loadings (n_components × 160) and a short description of each component.**
Standard implementation choices the method leaves to the analyst (the number of components,
signal normalisation, sign handling) should follow common practice.

Report, in plain terms, **the resting-state components / networks you find and whether the RSN
result holds on these data** — stating only what your analysis actually supports.

## Data

**Dataset:** ABIDE resting-state Dosenbach-160 ROI time series (`cpac`, band-pass filtered, no
global-signal regression), for the ABIDE **control** subjects, provided **in the container** at
`${BUNDLE_DIR}/dos160_ica.npz` (default `/opt/bundle`). Load it locally — **no network access is
available or needed** (the data is already present):

```python
import os, numpy as np
d = np.load(os.path.join(os.environ.get("BUNDLE_DIR", "/opt/bundle"), "dos160_ica.npz"),
            allow_pickle=True)
ts = d["ts"]   # object array of control subjects, each a (T x 160) float16 ROI time series
dx = d["dx"]   # diagnosis phenotype for those subjects (2 = control)
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `component_maps.csv` — the recovered component spatial maps / loadings: one row per component,
  160 columns (one per Dosenbach-160 ROI). This is the actual ICA result.
- `components.json` — the model order (number of components), `n_subjects`, and a short
  description of each component (e.g. its most strongly loading ROIs).
- `run_metadata.json` — dataset, atlas, number of subjects, and the ICA method / model order used.
- `findings.md` — a short written summary of the components / networks and whether the RSN result
  holds on these data. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `components.json`, and `findings.md`.
