# Interpreting a connectome classifier: which connections are affected in autism? (INTERP-001)

## Scientific context

A common goal in connectome studies of psychiatric conditions is to train a classifier that
distinguishes a patient group from controls using functional connectivity, and then to
**interpret the trained model** to report *which connections are altered in the condition*.
This "interpretable classifier" readout is the basis of connectome-based predictive modelling
(Shen et al., 2017, *Nature Protocols*, https://doi.org/10.1038/nprot.2016.178) and is also
central to graph-neural-network connectome models, which report edge/node **saliency** as the
affected connections. Reporting the connections a discriminative model relies on is a standard
way to say which edges are altered in a condition.

## Task

Using the nilearn ABIDE derivatives
(`nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_cc200"])`), form each
subject's functional connectivity over the **Craddock-200** parcellation (the vectorised
ROI×ROI correlation edges) and train a classifier to distinguish **autism** (`DX_GROUP == 1`)
from **controls** (`DX_GROUP == 2`). Then, **from your trained model, identify the connections
(edges) that are most affected in autism**, and **characterise** them — report the top affected
connections. Standard implementation choices the analysis leaves to the analyst (the classifier
family and regularisation, edge standardisation, temporal filtering) should follow common
practice.

Report, in plain terms, **which connections are most affected in autism on these data** —
stating only what your analysis actually supports.

## Data

**Dataset:** ABIDE resting-state (Craddock-200 ROI time series) with `DX_GROUP` in the
phenotypic table. Downloaded programmatically at runtime — nothing is pre-placed in the
container, so **internet access is required** on the first run (cached afterwards). Fetch it
with:

```python
nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_cc200"])
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `affected_connections.json` — the number of subjects/edges, the classifier used, and the top
  affected connections (or a summary of how they were identified).
- `run_metadata.json` — dataset, number of subjects, and the method used.
- `findings.md` — a short written summary of which connections are affected in autism. State
  only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `affected_connections.json`, and
`findings.md`.
