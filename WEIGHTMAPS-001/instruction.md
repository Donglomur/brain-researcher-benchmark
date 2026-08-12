# Interpreting a connectome classifier: which connections are affected in autism? (WEIGHTMAPS-001)

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

Using the provided ABIDE cc200 connectome bundle (`${BUNDLE_DIR}/cc200_interp.npz`), train a classifier to
distinguish **autism** (`y == 1`) from **controls** (`y == 2`) from each subject's functional
connectivity, then **from your trained model, identify the connections (edges) that are most
affected in autism**, and **characterise** them — report the top affected connections.

Standard implementation choices the analysis leaves to the analyst (the classifier family and
regularisation, edge standardisation, how you tune and validate the model) should follow common
practice.

Report, in plain terms, **which connections are most affected in autism on these data** —
stating only what your analysis actually supports.

## Data

**Dataset:** ABIDE cc200 connectomes, provided **in the container** at `${BUNDLE_DIR}/cc200_interp.npz`
(default `/opt/bundle`; **no download, no network available or needed** — the data is already present).
Load it locally, e.g.:

```python
import os, numpy as np
d = np.load(os.path.join(os.environ.get("BUNDLE_DIR", "/opt/bundle"), "cc200_interp.npz"),
            allow_pickle=True)
```

It holds:

- `X` — subjects × **19,900 edges**, the vectorised upper triangle of each subject's Craddock-200
  (cc200) ROI×ROI functional connectome (Pearson correlation, Fisher-z transformed). Edge column `k`
  corresponds to the ROI pair `numpy.triu_indices(200, 1)[:, k]` (both indices in `[0, 199]`).
- `y` — diagnosis per subject: **1 = autism (ASD)**, **2 = control (TD)**.
- `atlas`, `edges_upper_triangle_of` — provenance metadata (Craddock-200; upper triangle of 200).

~1,035 subjects. Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `affected_connections.json` — the number of subjects and edges, the classifier used, and the top
  affected connections (each as its ROI pair, with the value used to rank it) or a summary of how
  they were identified.
- `run_metadata.json` — dataset, number of subjects, and the method used.
- `findings.md` — a short written summary of which connections are affected in autism. State only
  what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason,
and still write parseable `run_metadata.json`, `affected_connections.json`, and `findings.md`.
