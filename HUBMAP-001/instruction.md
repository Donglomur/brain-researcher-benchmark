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
build the group connectome, compute node **centrality** (e.g. degree centrality / strength),
and **identify the principal hub regions** — the most central nodes. The Dosenbach-160 atlas
(`nilearn.datasets.fetch_coords_dosenbach_2010`) carries anatomical labels and network
assignments you can use to characterise where the hubs fall.

The standard analytic choices the analysis leaves to the analyst (correlation type, how you
define centrality) should follow common practice.

Report, in plain terms, **which regions are the principal functional-connectivity hubs on
these data** — stating only what your analysis actually supports.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `hubs.json` — `group_top_hubs` (the most central node indices, most-central first) and their
  centrality values; `n_subjects`.
- `run_metadata.json` — dataset, atlas, number of subjects, the centrality measure used, and
  the analytic choices you made.
- `findings.md` — a short written summary of the principal hubs and how confident you are in
  them. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `hubs.json`, and `findings.md`.
