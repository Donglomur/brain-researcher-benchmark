# Identifying the principal functional-connectivity hubs (HUBMAP-001)

## Scientific context

Highly connected **hub** regions are a standard summary of macroscale brain network
organisation: a small number of central nodes are thought to integrate information across
the connectome (Buckner et al., 2009, *J Neurosci*, https://doi.org/10.1523/JNEUROSCI.5062-08.2009;
van den Heuvel & Sporns, 2013). Identifying the principal hubs of the resting-state
functional connectome is a common analysis goal.

## Task

Using the nilearn-pinned ABIDE derivatives
(`nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_dosenbach160"])`), form
each subject's ROI×ROI functional connectivity matrix over the **Dosenbach-160** parcellation,
build the group connectome, compute node **centrality**,
and **identify the principal hub regions** — the most central nodes. The Dosenbach-160 atlas
(`nilearn.datasets.fetch_coords_dosenbach_2010`) carries anatomical labels and network
assignments you can use to characterise where the hubs fall.

Report, in plain terms, **which regions are the principal functional-connectivity hubs on
these data**.

## Data

**Dataset:** ABIDE resting-state (Dosenbach-160) + Dosenbach coords. It is downloaded programmatically at runtime by the loader used in the Task section — nothing is pre-placed in the container, so **internet access is required** on the first run (the download is cached locally afterwards). Fetch it with:

```python
nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_dosenbach160"], quality_checked=True); nilearn.datasets.fetch_coords_dosenbach_2010()
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `hubs.json` — `group_top_hubs` (the most central node indices, most-central first) and their
 centrality values; `n_subjects`.
- `run_metadata.json` — dataset, atlas, number of subjects, the centrality measure used, and
 the analytic choices you made.
- `findings.md` — a short written summary of the principal hubs.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `hubs.json`, and `findings.md`.
