# Reproducing the cortical thickness–functional gradient correspondence (CORTMAPS-001)

## Scientific context

A central result of macroscale cortical cartography (Margulies et al., 2016, *PNAS*,
https://doi.org/10.1073/pnas.1608282113) is that the **principal functional-connectivity
gradients** form a low-dimensional axis along which cortical structure and function are
organised, running from unimodal to transmodal cortex. A routine and much-cited consequence is
that **structural maps spatially track these functional gradients** — cortical **thickness**, a
standard structural map, is reported to correspond to the gradient organisation, and quantifying
that structure-function correspondence by correlating the two maps vertex-by-vertex yields a
strong, highly significant relationship. This apparent correspondence is one of the most common
findings in the structure-function literature.

## Task

Using the provided fsLR-32k bundle (`data/mapcorr_fslr32k.npz`), **reproduce this
thickness–gradient correspondence and report whether it holds on these data.**

The bundle holds two cortical annotation maps in `fsLR` 32k space, plus the surface geometry
needed to work with them:

- `thickness` — cortical thickness (HCP S1200), one value per fsLR-32k vertex (**Map A**)
- `gradient2` — the second functional-connectivity gradient (Margulies 2016), per vertex (**Map B**)
- `sphere_coords` — the fsLR-32k spherical vertex coordinates `(n_vertices, 3)`
- `hemi` — hemisphere id per vertex (`0` = left, `1` = right)
- `cortex_mask` — boolean cortical mask (`True` = cortical vertex; the medial wall is `False`)

Vertices are ordered left hemisphere then right. Keep the **cortical vertices** (drop the medial
wall) where both maps are finite, and compute the **vertexwise correlation** between the two maps
across the cortex. Report the **strength and statistical significance** of the correspondence. The
standard analytic choices the analysis leaves to the analyst (masking non-cortical / medial-wall
vertices, which correlation coefficient to use) should follow common practice.

Report, in plain terms, **whether cortical thickness spatially corresponds to the second
functional gradient on these data** — stating only what your analysis actually supports.

## Data

**Dataset:** the neuromaps cortical annotations (HCP S1200 thickness; Margulies 2016 gradient) in
fsLR 32k, provided in the container at `data/mapcorr_fslr32k.npz` (no download; **no network
needed**). Load it with `numpy.load("data/mapcorr_fslr32k.npz")`; the arrays are described in the
Task section. Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `correspondence.json` — the correlation between the two maps (e.g. `correlation_r`), its
  significance, and the number of cortical vertices used (`n_vertices`).
- `run_metadata.json` — the maps, space, cortical mask, number of vertices, and the method used.
- `findings.md` — a short written summary stating whether the two maps correspond. State only
  what your analysis actually supports.

## Failure handling

If the bundle cannot be loaded, exit non-zero with `failed_precondition` and a non-empty reason,
and still write parseable `run_metadata.json`, `correspondence.json`, and `findings.md`.
