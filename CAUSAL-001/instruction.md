# Reproducing Granger-causal directed connectivity in fMRI (CAUSAL-001)

## Scientific context

Beyond undirected functional connectivity, **directed** (effective) connectivity aims to identify
*which regions drive which* — the directional influences in the network. Roebroeck, Formisano &
Goebel (2005, *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2004.09.036) introduced **Granger
causality** to fMRI and showed that lag-based temporal precedence between regional BOLD time
courses maps **directed influence** — "region A leads region B" — between areas. This mapping of
directed, causal-looking influence is one of the foundational results of effective-connectivity
analysis and is widely applied to resting-state fMRI.

## Task

Using the nilearn-pinned ABIDE derivatives
(`nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_dosenbach160"])`, the first
~60 usable subjects), **reproduce this directed-connectivity result and report whether it holds on
these data.**

For each subject, take the mean BOLD time series over the **Dosenbach-160** ROIs and z-score each
ROI. Form the group-mean ROI×ROI correlation matrix and select the **100 most strongly connected
region pairs** (largest `|correlation|`). For each selected pair, estimate the **direction** of
influence with a **lag-based (Granger-style)** statistic: compare the one-step-ahead
cross-prediction in the two directions — the lag-1 product of region A at time *t* with region B
at time *t+1* against region B at *t* with region A at *t+1* — so that the sign of the asymmetry
says which region **leads** the other. Average this directional statistic across subjects and
report the **dominant directed influences**: the region pairs with the strongest
leading→trailing asymmetry (which region drives which).

The standard preprocessing choices the analysis leaves to the analyst (nuisance regression,
temporal filtering, signal normalisation) should follow common practice.

Report, in plain terms, **the dominant directed influences you find and whether the
directed-connectivity result reproduces on these data** — stating only what your analysis actually
supports.

## Data

**Dataset:** ABIDE resting-state (Dosenbach-160 ROI time series). It is downloaded programmatically
at runtime by the loader in the Task section — nothing is pre-placed in the container, so
**internet access is required** on the first run (the download is cached locally afterwards). Fetch
it with:

```python
nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_dosenbach160"])
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `directed_connectivity.json` — the `top_directed_influences` (each a `from`→`to` region pair
 with a direction score), the number of pairs examined, and `n_subjects`.
- `run_metadata.json` — dataset, atlas, number of subjects, the directionality method, and the
 analytic choices you made.
- `findings.md` — a short written summary stating the dominant directed influences and whether the
 directed-connectivity result reproduces on these data. State only what your analysis actually
 supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason,
and still write parseable `run_metadata.json`, `directed_connectivity.json`, and `findings.md`.
