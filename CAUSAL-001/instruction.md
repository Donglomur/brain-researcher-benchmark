# Estimating directed functional connectivity (CAUSAL-001)

## Scientific context

Beyond undirected functional connectivity, **directed** (effective) connectivity aims to
identify *which regions drive which* — the directional influences in the network. Granger-
causality and lag-based methods applied to fMRI were introduced to map such directed influences
(Roebroeck et al., 2005, *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2004.09.036) and are
widely used on resting-state data.

## Task

Using the nilearn-pinned ABIDE derivatives
(`nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_dosenbach160"])`),
estimate the **directed functional connectivity** among the most strongly connected regions
using a **lag-based (Granger-style)** approach, and identify the **dominant directed
influences** — which region leads / drives which.

The standard analytic choices the analysis leaves to the analyst (lag, how many pairs, how you
score directionality) should follow common practice.

Report, in plain terms, **the dominant directed influences you find in the resting-state
network on these data** — stating only what your analysis actually supports.

## Data

**Dataset:** ABIDE resting-state (Dosenbach-160). It is downloaded programmatically at runtime by the loader used in the Task section — nothing is pre-placed in the container, so **internet access is required** on the first run (the download is cached locally afterwards). Fetch it with:

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
- `findings.md` — a short written summary of the dominant directed influences and how confident
  you are in them. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `directed_connectivity.json`, and
`findings.md`.
