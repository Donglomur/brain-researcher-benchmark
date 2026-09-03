# Self-referential strongest projections in the mouse mesoscale connectome (ALLENCONN-001)

## Scientific context

The Allen Mouse Brain Connectivity Atlas (Oh et al. 2014, *Nature*,
https://doi.org/10.1038/nature13186) mapped brain-wide axonal projections with
anterograde rAAV tracer injections and summarised inter-region connectivity as a matrix
of projection strengths over a standard set of anatomical structures. One basic
descriptor of such a connectome is how **self-referential** each region's projections
are: for how many source regions is the *strongest* outgoing projection to the region's
own structure, rather than to a distant one.

## Task

Using the Allen Mouse Connectivity Atlas through
`allensdk.core.mouse_connectivity_cache.MouseConnectivityCache`, build the directed
region-by-region projection-strength matrix for the **wild-type** anterograde experiments
over the standard **316 "summary structure"** set, and report the **fraction of source
regions whose strongest projection target is their own structure** — i.e. for each source
region take its strongest target (the summary structure with the largest projection
strength in that source's row, **including the source's own structure**), and report the
fraction of source regions for which that strongest target is the source's own structure.

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

Build the matrix as a directed **source-region × target-structure** array. Each
experiment's source region is its **primary injection structure** mapped onto the
316-structure summary set (an injection structure that is finer than a summary structure
maps to its summary-structure ancestor). The matrix has **one row per source region that is
the primary injection site of at least one wild-type experiment** (source regions never
injected are not rows). The entry for (source region, target structure) is the **mean
`projection_density`** across the experiments that share that source region, evaluated in
that target structure. For each source region, the **strongest target** is the summary
structure (over all 316, the source's own structure included) with the largest entry in
that source's row; report the fraction of source regions whose strongest target is their
own structure.

Standard bookkeeping that the analysis leaves to you — exactly how you resolve an injection
structure to its summary-structure ancestor, how you assemble the per-experiment structure
vectors into the matrix — should follow common practice for this atlas.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `connectivity_matrix.csv` — the directed source-region × target-structure
  projection-strength matrix (one row per injected source summary structure; columns are
  the 316 target summary structures; a header row/column of structure acronyms or ids).
- `self_projection.json` — at least
  `{"self_strongest_fraction": <float>, "n_source_regions": <int>,
  "n_self_strongest": <int>, "n_experiments": <int>, "n_target_structures": <int>}`.
- `run_metadata.json` — cache/atlas version, dataset id, number of experiments used,
  the structure set, the connection metric, and the bookkeeping choices you made.
- `findings.md` — a short written summary (a few sentences): the self-strongest fraction
  you obtained and what it says about how self-referential the mouse mesoscale connectome
  is. State only what your analysis actually supports.

## Failure handling

If the Allen cache cannot be resolved (the atlas manifest or the structure-unionize data
cannot be downloaded), exit non-zero with `failed_precondition` and a non-empty reason, and
still write a parseable `run_metadata.json`, `self_projection.json`, and `findings.md`.
