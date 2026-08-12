# Community structure of the functional connectome (NETMODULES-001)

## Scientific context

A foundational result in network neuroscience is that the resting-state functional connectome is
**modular** — it partitions into a set of communities / networks (Power et al., 2011, *Neuron*,
https://doi.org/10.1016/j.neuron.2011.09.006; Yeo et al., 2011). The community structure — how
many modules the brain has and which regions belong to each — is the headline object of these
analyses and one of the most reported summaries of brain network organisation.

## Task

Using the provided ABIDE Dosenbach-160 connectome bundle (see **Data**), build the **group-mean
functional connectome** over the **typically-developing control subjects** (the `dx == 2` group)
and **characterise its community / modular structure** — how many communities it partitions into
and which regions belong to each.

Reconstruct the group-mean 160×160 region-by-region connectome from the packaged edges (retain the
positive-weight structure, zero the diagonal), and apply **Louvain modularity maximisation** at its
standard default resolution to recover the modules. Report how many communities the connectome
partitions into and the community assignment of the regions. Standard implementation choices the
cited methods leave to the analyst (edge weighting / thresholding, the exact community-detection
settings) should follow common practice; the brief does not spell them out.

Summarise your characterisation of the connectome's community structure in `findings.md`,
stating only what your analysis actually supports.

## Data

**Dataset:** ABIDE resting-state Dosenbach-160 connectomes (`cpac`, band-pass filtered, no
global-signal regression), provided **in the container** at `${BUNDLE_DIR}/dos160_modular.npz`
(default `/opt/bundle`) — nothing is downloaded and **no network access is required or available**
(the data is already present). Load it locally with `numpy.load(..., allow_pickle=True)`:

```python
import os, numpy as np
d = np.load(os.path.join(os.environ.get("BUNDLE_DIR", "/opt/bundle"), "dos160_modular.npz"),
            allow_pickle=True)
```

It holds:

- `X` — subjects × **12,720** edges: the upper triangle of each subject's 160×160 Dosenbach-160
  connectome, Pearson correlation, Fisher-z transformed (`arctanh`). Reconstruct a subject's full
  symmetric 160×160 matrix by placing `X[i]` on `numpy.triu_indices(160, 1)` and symmetrising.
- `dx` — diagnosis per subject (`1` = ASD, `2` = typically-developing control).
- `subid` — subject IDs.
- `atlas`, `n_roi` (= 160), `edges_upper_triangle_of` (= 160) — provenance scalars.

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `communities.json` — the number of modules (e.g. `n_modules`), the per-region community
  assignment (a list of integer module labels, one per Dosenbach-160 region), and `n_subjects`.
- `run_metadata.json` — dataset, atlas, number of subjects, population, and the community-detection
  method used.
- `findings.md` — a short written summary of the community structure. State only what your analysis
  actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason,
and still write parseable `run_metadata.json`, `communities.json`, and `findings.md`.
