# Audit and reconstruct human–mouse Purkinje dendritic morphology

You are reproducing a central morphology analysis from Busch & Hansel, *Non-allometric expansion and enhanced compartmentalization of Purkinje cell dendrites in the human cerebellum*, eLife 14:RP105013 (2025), https://doi.org/10.7554/eLife.105013.3. Reconstruct the neuronal trees, audit their consistency with released author measurements, and determine which conclusions these files support. This is a bounded public development reproduction audit, not a request to force agreement with published species averages or demonstrate a new scientific advance.

Inputs are in `/input`: `cells.json` maps ten raw SWCs to species/source filenames; `raw/` contains the unchanged reconstructions from https://zenodo.org/records/15066697 (CC-BY-4.0). `author_sholl_totals.csv` exposes author-derived per-cell totals explicitly for source reconciliation. These are answer-bearing summaries; copying them does not reconstruct the trees. A pinned excerpt with exact line numbers and source hash is provided in `/input/source_semantics.json`. The original analysis notebook is https://zenodo.org/api/records/15066697/files/HumanvsMousePaperAnalysis.Rmd/content. It is a source-available condition; the runtime has no network. No author-code/no-code causal comparison is claimed.

The paper reports five cells per species from three human and two mouse individuals. Mouse cell-to-individual assignments are unavailable in these filenames. Do not fabricate them, treat thousands of branches as independent animals, or infer functional compartmentalization from anatomy alone. Some source files may not have the same schema or analysis version as the author summaries. Preserve every file and component, and diagnose discrepancies.

## Required analysis

1. Parse seven- or nine-column SWC: node ID, type, x/y/z (µm), radius (µm), parent ID, and optional author section/order. A parent of -1 denotes a root. Validate unique positive integer node IDs, integer parent IDs/types, finite coordinates, nonnegative radii, existing parents, and absence of cycles. Forests are valid audit inputs; do not silently retain only the largest component. Sort nodes by ID when emulating the author's sample order.
2. Compute each non-root edge's 3D Euclidean length, retaining all point types and all components. Sum every edge once. Contract maximal degree-one paths into graph branch segments: a path starts at a root or node whose number of children is not one, follows one outgoing child, and ends at a leaf or the next node whose number of children is not one. Its centrifugal order is 1 out of a root and increments at every subsequent node with more than one child. A terminal path ends at a leaf. For edge-caliber sensitivity, use the mean of endpoint diameters (equivalently the sum of endpoint radii), and weight these diameters by edge length for each path's mean.
3. Reimplement the notebook's retained-section calculation for **only nine-column files**, under two explicit Size conventions (Fig1O/P). The notebook declares radius-to-diameter conversion at line313, then reloads `d` at485–488 without that conversion before the section loop. Its historical execution state is unknown; do not call either variant unchanged author-runtime reproduction. Select the section labels present on non-soma nodes, then take every node carrying each selected label, including any same-label soma rows. Skip these selected-label groups with fewer than two samples **before** adding any parent. If the first sample's type is not 5, prepend its parent. Sum successive 3D distances in this ordered list. Compute (a) `declared_diameter_um`: twice the mean radius over all rows except the first, and (b) `reloaded_size_um`: mean raw radius over those identical rows. Section order is the second final-list row's supplied order. Separately apply <=1.310202 to each convention and calculate retained-length-weighted fractions; do not select one by its agreement with paper numbers. The reloaded-Size alternative audits a state ambiguity, not a physically appropriate substitute for diameter. Do not synthesize missing author labels for seven-column files. These section estimands and the graph-complete estimator differ.
4. Compare graph totals with the exposed author Sholl totals. For the explicitly retrospective descriptive subset, define eligibility as one connected component and absolute relative length discrepancy <=0.001, where signed relative discrepancy is `(graph_length-author_total)/author_total`. This threshold was set during task construction after seeing a source discrepancy; it is not a preregistered biological exclusion. Do not substitute author totals for raw results or interpret this selected subset as new confirmation.
5. Report cell-weighted species means/sample SDs for eligible cells; mean human length divided by mean mouse length; leave-one-cell-out ratios and human-minus-mouse mean edge-thin-fraction differences at 1.310202. For thresholds 1.0, 1.310202, and 1.6 µm, calculate the fraction of raw edge length below threshold. Also report the mean fractions on the matched set of annotated cells to distinguish estimator sensitivity from different cell inclusion. This is robustness analysis on exposed observations, not heldout improvement.

## Program and numerical interface

Submit one UTF-8 Python source file, at most131,072 bytes. It runs offline as `python -I /program/program.py --input /input --out /output` with NumPy/Pandas available,60 seconds,1.75CPU/3GiB and a fresh output tree. Top-level code and any valid implementation are allowed: no function names, AST function presence, source style or explanation length is graded. No source or private target file is mounted beyond your own program and the declared public inputs.

Write exactly `cells.csv`, `branches.csv`, `author_sections.csv`, `components.csv`, `summary.json`. Optionally write `interpretation.json`, retained as opaque prose and never parsed or scored. Do not write `reproduce.py` or extra files. Per-file caps are500,000 /4,000,000 /3,000,000 /250,000 /200,000 bytes respectively; optional prose20,000 bytes; aggregate8,000,000 bytes. CSV row and column order are free, exact named columns and unique keys required. Do not replace missing annotation fields with fabricated zeros. Numeric tokens must be finite, at most128 characters; values too small to survive binary64 conversion as nonzero are invalid. JSON integer literals are limited to18 characters; larger finite magnitudes may use decimal/exponent spelling.

All10 released cells,13 components, both caliber conventions and the declared descriptive summaries are required. Output identities and expected missingness are checked independently of numerical accuracy. Missing/extra topology keys or unexpected blanks produce explicit incomplete coverage with no matched-subset numerical score. The structural requirement fixes denominators; it is not a minimum accuracy threshold.

The primary metric is the square root of the equally weighted mean of the10 within-cell mean squared branch-length errors, in micrometres. Every other numerical column has separate native-unit error diagnostics, with per-cell denominators retained and equal-cell RMSE where defined. Counts/flags also report exact mismatches. Summary errors are reported individually. A primary error of zero alone does not certify full numerical reconstruction: caliber, thin fractions, counts and summaries can still be wrong, and their separate diagnostics remain part of the result. No mixed-unit composite, insight reward or ordinary accuracy floor is used. Row keys and source metadata remain exact; finite wrong quantities receive their continuous errors. Numerical overflow is explicitly unscorable.

Automated numerical comparison does not establish source originality, correct method use, new scientific insight, donor-level inference or the full paper. All released observations and author Sholl totals are exposed development material. Source excerpt assistance is explicit; no paper-only versus official-code experiment is qualified. Optional interpretation may be reviewed separately, but cannot change this numerical score.

`cells.csv` columns:
`cell_id,species,n_nodes,n_components,n_tips,n_segments,max_order,graph_length_um,author_sholl_length_um,relative_export_difference,analysis_eligible,has_author_sections,author_retained_sections,author_retained_length_um,declared_diameter_thin_fraction,reloaded_size_thin_fraction,edge_thin_fraction_1.0,edge_thin_fraction_1.310202,edge_thin_fraction_1.6`

Counts/order refer to all components; `n_tips` includes every childless node; `max_order` is maximum graph order. `analysis_eligible`/`has_author_sections` are 0/1. Retained section count/length and both convention-specific fractions are blank for files without annotations. Retained length sums the included section lengths. Each convention-specific fraction divides its below-threshold retained length by that same total retained length.

`branches.csv` columns:
`cell_id,start_id,end_id,component_root,order,terminal,n_edges,length_um,mean_edge_diameter_um`

Key `(cell_id,start_id,end_id)`. Root ID identifies the originating component. `terminal` is 0/1. Mean diameter is edge-length weighted; for zero-length paths use 0. Every raw edge must appear in exactly one maximal path.

`author_sections.csv` columns:
`cell_id,section_id,original_nodes,length_um,declared_diameter_um,reloaded_size_um,order`

Key `(cell_id,section_id)`, retained sections only; `original_nodes` is the sample count before conditional parent insertion.

`components.csv` columns:
`cell_id,root_id,n_nodes,length_um,n_tips`

`summary.json` must have exactly these keys:

- `schema_version`: 1.
- `analysis_scope`: `post_inspection_source_consistent_subset_descriptive`.
- `species`: object keyed `human`, `mouse`. Each value has `n_cells`, `mean_length_um`, `sd_length_um`, `mean_segments`, `sd_segments`, `mean_max_order`, and `edge_thin_fraction_1.0`, `edge_thin_fraction_1.310202`, `edge_thin_fraction_1.6` (arithmetic means across eligible cells; sample SD uses ddof=1).
- `human_mouse_length_ratio`: ratio of cell means in the eligible subset.
- `leave_one_cell_out`: one object per eligible cell, sorted by `cell_id`, with `omitted_cell`, `length_ratio`, `edge_thin_difference` (human-minus-mouse mean fractions at 1.310202 after that omission).
- `section_estimator_conventions`: keyed by species, each with `n_cells`, `mean_declared_diameter_thin_fraction`, `sd_declared_diameter_thin_fraction`, `mean_reloaded_size_thin_fraction`, `sd_reloaded_size_thin_fraction`, over cells with supplied annotations. Both SDs use ddof=1.
- `matched_annotated_edge_estimator`: keyed by species, each with `n_cells` and the three `edge_thin_fraction_*` means over those same annotated cells.
- `excluded_from_subset`: cell IDs sorted alphabetically.
- `paper_reported_n_individuals`: `{"human":3,"mouse":2}`; these are paper-reported counts, not newly established mappings.

