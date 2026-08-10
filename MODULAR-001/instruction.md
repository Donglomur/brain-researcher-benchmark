# Community structure of the functional connectome (MODULAR-001)

## Scientific context

A foundational result in network neuroscience is that the resting-state functional connectome is
**modular** — it partitions into a set of communities / networks (Power et al., 2011, *Neuron*,
https://doi.org/10.1016/j.neuron.2011.09.006; Yeo et al., 2011). The community structure — how
many modules the brain has and which regions belong to each — is the headline object of these
analyses and one of the most reported summaries of brain network organisation.

## Task

Using the nilearn-pinned ABIDE derivatives
(`nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_dosenbach160"], quality_checked=True)`),
build the group functional connectome over the **Dosenbach-160** parcellation and **characterise
its community / modular structure** — how many communities it partitions into and which regions
belong to each.

For each subject take the ROI×ROI correlation matrix; form the **group-mean connectome** (retain
the positive-weight structure, zero the diagonal); and apply **community detection** (e.g. Louvain
modularity maximisation) to recover the modules. Report how many communities the connectome
partitions into and the community assignment of the regions. Standard implementation choices the
cited methods leave to the analyst (edge weighting / thresholding, the community-detection
algorithm and its settings, temporal filtering) should follow
common practice; the brief does not spell them out.

Summarise your characterisation of the connectome's community structure in `findings.md`,
stating only what your analysis actually supports.

## Data

**Dataset:** ABIDE resting-state (Dosenbach-160 ROI time series). It is downloaded
programmatically at runtime by the loader in the Task section — nothing is pre-placed in the
container, so **internet access is required** on the first run (the download is cached locally
afterwards). Fetch it with:

```python
nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_dosenbach160"], quality_checked=True)
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `communities.json` — the number of modules (e.g. `n_modules`) and the community assignment of
  the regions; `n_subjects`.
- `run_metadata.json` — dataset, atlas, number of subjects, and the community-detection method
  used.
- `findings.md` — a short written summary of the community structure. State only what your
  analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `communities.json`, and `findings.md`.
