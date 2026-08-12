# Reproducing the association-cortex hub finding (CORTHUBS-001)

## Scientific context

Highly connected **hub** regions are a standard summary of macroscale brain network
organisation: a small number of central nodes are thought to integrate information across the
connectome. Buckner et al. (2009, *J Neurosci*, https://doi.org/10.1523/JNEUROSCI.5062-08.2009;
see also van den Heuvel & Sporns, 2013) reported that the degree-centrality hubs of the
intrinsic connectivity network concentrate in **heteromodal association cortex overlapping the
default network** (medial prefrontal, posterior cingulate/precuneus, lateral parietal), **not**
primary sensorimotor/visual cortex. Identifying these principal hubs of the resting-state
functional connectome is one of the most-cited summaries of brain network organisation.

## Task

Using the provided ABIDE Dosenbach-160 connectome bundle (`data/dos160_hubmap.npz`; see **Data**),
**reproduce this association-cortex hub finding and report whether it holds on these data.**

Work from the **control subjects** (`dx == 2`). For each subject, the bundle gives the ROI×ROI
functional connectome (Fisher-z Pearson correlation over the Dosenbach-160 parcellation), stored
as its **upper triangle** (12,720 edges). Compute each node's **weighted degree centrality (node
strength)** — the sum of its positive connections to all other nodes — and **average the node
strengths across subjects** to build the group hub map. Rank the nodes and **identify the
principal hub regions** (the most central nodes). The bundle also carries the Dosenbach-160
**network labels, anatomical labels, and MNI coordinates** — use them to characterise **where the
hubs fall** (which cortical systems), and compare that against the atlas base rates.

Report, in plain terms, **which regions are the principal hubs and whether the association-cortex
hub finding reproduces on these data** — stating only what your analysis actually supports.

## Data

**Dataset:** ABIDE resting-state Dosenbach-160 connectomes (`cpac`, band-pass filtered, no
global-signal regression), **provided in the container** at `${BUNDLE_DIR}/dos160_hubmap.npz`
(default `/opt/bundle`) — nothing is downloaded, **no network access is available or needed** (the
data is already present). Load it locally:

```python
import os, numpy as np
d = np.load(os.path.join(os.environ.get("BUNDLE_DIR", "/opt/bundle"), "dos160_hubmap.npz"),
            allow_pickle=True)
```

It holds:

- `X` — subjects × **12,720** Fisher-z edges (the upper triangle of each subject's 160×160
  Dosenbach-160 connectome; reconstruct the symmetric matrix with `numpy.triu_indices(160, 1)`),
- `dx` — diagnosis per subject (**1 = autism, 2 = control**),
- `networks`, `labels`, `coords` — the Dosenbach-160 canonical network assignment, anatomical
  label, and MNI (x, y, z) coordinate for each of the 160 ROIs,
- `atlas`, `edges_upper_triangle_of` — provenance metadata.

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `hubs.json` — `group_top_hubs` (the most central node indices, most-central first) and their
  centrality values; `n_subjects`.
- `run_metadata.json` — dataset, atlas, number of subjects, the centrality measure used, and the
  analytic choices you made.
- `findings.md` — a short written summary stating which regions are the principal hubs and
  whether the association-cortex hub finding reproduces on these data. State only what your
  analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `hubs.json`, and `findings.md`.
