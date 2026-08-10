# Community structure of the functional connectome (MODULAR-001)

## Scientific context

A foundational result in network neuroscience is that the resting-state functional connectome is
**modular** — it partitions into a set of communities / networks (Power et al., 2011, *Neuron*,
https://doi.org/10.1016/j.neuron.2011.09.006; Yeo et al., 2011). Identifying the community
structure — how many modules the brain has and which regions belong to each — is a common
analysis goal.

## Task

Using the nilearn-pinned ABIDE derivatives
(`nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_dosenbach160"])`), build
the group functional connectome over the **Dosenbach-160** parcellation and compute its
**community / modular structure**. **Report how many
modules (communities) the connectome has and the community assignment** of the regions.

Report, in plain terms, **the modular / community structure of the connectome on these data**.

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
- `run_metadata.json` — dataset, atlas, number of subjects, and the community-detection method used.
- `findings.md` — a short written summary of the community structure.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `communities.json`, and `findings.md`.
