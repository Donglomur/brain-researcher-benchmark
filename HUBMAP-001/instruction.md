# Reproducing the association-cortex hub finding (HUBMAP-001)

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

Using the nilearn-pinned ABIDE derivatives
(`nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_dosenbach160"], quality_checked=True)`,
the control subjects, `DX_GROUP == 2`), **reproduce this association-cortex hub finding and
report whether it holds on these data.**

For each subject, form the **ROI×ROI functional connectivity matrix** (Pearson correlation)
over the **Dosenbach-160** parcellation, and compute each node's **weighted degree centrality
(node strength)** — the sum of its positive correlations to all other nodes. **Average the node
strengths across subjects** to build the group connectome, rank the nodes, and **identify the
principal hub regions** (the most central nodes). The Dosenbach-160 atlas
(`nilearn.datasets.fetch_coords_dosenbach_2010`) carries anatomical labels and canonical
network assignments — use them to characterise **where the hubs fall** (which cortical systems),
and compare that against the atlas base rates. The standard preprocessing choices the analysis
leaves to the analyst (nuisance regression, temporal filtering, signal normalisation) should
follow common practice.

Report, in plain terms, **which regions are the principal hubs and whether the association-cortex
hub finding reproduces on these data** — stating only what your analysis actually supports.

## Data

**Dataset:** ABIDE resting-state (Dosenbach-160) + Dosenbach coords. It is downloaded
programmatically at runtime by the loader used in the Task section — nothing is pre-placed in
the container, so **internet access is required** on the first run (the download is cached
locally afterwards). Fetch it with:

```python
nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_dosenbach160"], quality_checked=True); nilearn.datasets.fetch_coords_dosenbach_2010()
```

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
