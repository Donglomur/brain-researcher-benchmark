# How dense is the mouse mesoscale projection connectome? (ALLENCONN-001)

## Scientific context

The Allen Mouse Brain Connectivity Atlas (Oh et al. 2014, *Nature*,
https://doi.org/10.1038/nature13186) mapped brain-wide axonal projections with
anterograde rAAV tracer injections and summarised inter-region connectivity as a matrix
of projection strengths over a standard set of anatomical structures. A first-order
descriptor of any such connectome is how *dense* it is: what fraction of the possible
region-to-region connections actually carry appreciable projection signal.

## Task

Using the Allen Mouse Connectivity Atlas through
`allensdk.core.mouse_connectivity_cache.MouseConnectivityCache`, build the directed
region-by-region projection-strength matrix for the **wild-type** anterograde experiments
over the standard **316 "summary structure"** set, and report the **fraction of
region-pairs that are strongly connected** — region-pairs whose projection density
exceeds **0.1**.

Pin the following so the reported fraction is well-defined:

- **Experiments:** all wild-type (non-transgenic) injection experiments —
  `MouseConnectivityCache.get_experiments(cre=False)`.
- **Structures:** the 316 summary structures, i.e. the structure set with
  `structure_set_id = 167587189`
  (`structure_tree.get_structures_by_set_id([167587189])`).
- **Connection strength:** `projection_density` from the structure-unionize records
  (`get_structure_unionizes`).
- **Hemisphere:** read the whole-structure unionize value that spans both hemispheres
  (`hemisphere_id = 3`).
- **Strong-connection threshold:** projection density **> 0.1**.

Build the matrix as a directed **source-region × target-structure** array. Each
experiment's source region is its **primary injection structure** mapped onto the
316-structure summary set (an injection structure that is finer than a summary structure
maps to its summary-structure ancestor). The matrix has **one row per source region that is
the primary injection site of at least one wild-type experiment** (source regions never
injected are not rows). The entry for (source region, target structure) is the **mean
`projection_density`** across the experiments that share that source region, evaluated in
that target structure. The strong-connection fraction is the fraction of the matrix's
entries that exceed the threshold.

Standard bookkeeping that the analysis leaves to you — exactly how you resolve an injection
structure to its summary-structure ancestor, how you assemble the per-experiment structure
vectors into the matrix — should follow common practice for this atlas.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `connectivity_matrix.csv` — the directed source-region × target-structure
  projection-strength matrix (one row per injected source summary structure; columns are
  the 316 target summary structures; a header row/column of structure acronyms or ids).
- `strong_fraction.json` — at least
  `{"strong_fraction": <float>, "threshold": 0.1, "n_region_pairs": <int>,
  "n_strong_pairs": <int>, "n_experiments": <int>, "n_source_regions": <int>,
  "n_target_structures": <int>}`.
- `run_metadata.json` — cache/atlas version, dataset id, number of experiments used,
  the structure set, the connection metric, the threshold, and the bookkeeping choices you
  made.
- `findings.md` — a short written summary (a few sentences): the strong-connection fraction
  you obtained and what it says about how dense the mouse mesoscale connectome is. State
  only what your analysis actually supports.

## Failure handling

If the Allen cache cannot be resolved (the atlas manifest or the structure-unionize data
cannot be downloaded), exit non-zero with `failed_precondition` and a non-empty reason, and
still write a parseable `run_metadata.json`, `strong_fraction.json`, and `findings.md`.
