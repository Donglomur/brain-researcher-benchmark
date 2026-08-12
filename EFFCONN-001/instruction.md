# Reproducing Granger-causal directed connectivity in fMRI (EFFCONN-001)

## Scientific context

Beyond undirected functional connectivity, **directed** (effective) connectivity aims to identify
*which regions drive which* — the directional influences in the network. Roebroeck, Formisano &
Goebel (2005, *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2004.09.036) introduced **Granger
causality** to fMRI and showed that lag-based temporal precedence between regional BOLD time
courses maps **directed influence** — "region A leads region B" — between areas. This mapping of
directed, causal-looking influence is one of the foundational results of effective-connectivity
analysis and is widely applied to resting-state fMRI.

## Task

Using the provided ABIDE Dosenbach-160 timeseries bundle (`data/dos160_causal.npz`; see **Data**),
**reproduce this directed-connectivity result and report whether it holds on these data.**

For each subject, take the Dosenbach-160 ROI time series and z-score each ROI. Form the group-mean
ROI×ROI correlation matrix and select the **100 most strongly connected region pairs** (largest
`|correlation|`). For each selected pair, estimate the **direction** of influence with a proper
**Granger-causality** test: fit a bivariate **first-order vector-autoregressive (VAR(1))** model to
the pair and test whether the past of one region improves the one-step-ahead prediction of the other
beyond that region's own past — an **F-test on the lagged cross-term** (equivalently, the log-ratio
of restricted vs full residual variance). The direction with the stronger Granger influence is the
inferred driver. Aggregate the directed influence across subjects and report the **dominant directed
influences**: the region pairs with the strongest driver→target Granger asymmetry (which region
drives which).

The standard preprocessing choices the analysis leaves to the analyst (nuisance regression,
temporal filtering, signal normalisation) should follow common practice.

Report, in plain terms, **the dominant directed influences you find and whether the
directed-connectivity result reproduces on these data** — stating only what your analysis actually
supports.

## Data

**Dataset:** ABIDE resting-state Dosenbach-160 ROI time series (`cpac`, band-pass filtered, no
global-signal regression), provided **in the container** at `${BUNDLE_DIR}/dos160_causal.npz`
(default `/opt/bundle`). Load it locally — **no network access is available or needed** (the data is
already present):

```python
import os, numpy as np
d = np.load(os.path.join(os.environ.get("BUNDLE_DIR", "/opt/bundle"), "dos160_causal.npz"),
            allow_pickle=True)
ts = d["ts"]   # object array of 250 subjects, each a T x 160 float16 Dosenbach-160 ROI time series
dx = d["dx"]   # diagnosis per subject (1 = ASD, 2 = TD)
```

- `ts` — an **object array of 250 subjects**, each a `T×160` `float16` array of Dosenbach-160 ROI
  time series (`T` ≈ 150–316 time points per subject; the raw per-subject timeseries, so you can fit
  a VAR model and split a run).
- `dx` — diagnosis per subject (1 = ASD, 2 = TD); `atlas` = "Dosenbach-160"; `n_roi` = 160.

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `directed_connectivity.json` — the `top_directed_influences` (each a `from`→`to` region pair with
  a Granger score), the number of pairs examined (`n_pairs`), and `n_subjects`.
- `directed_influences.csv` — a per-pair table of the directed influences you estimated (the ROI
  indices of each examined pair and their Granger statistics).
- `run_metadata.json` — dataset, atlas, number of subjects, the directionality method, and the
  analytic choices you made.
- `findings.md` — a short written summary stating the dominant directed influences and whether the
  directed-connectivity result reproduces on these data. State only what your analysis actually
  supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason,
and still write parseable `run_metadata.json`, `directed_connectivity.json`, and `findings.md`.
