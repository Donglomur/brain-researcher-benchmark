# Spatial correspondence between two cortical maps (MAPCORR-001)

## Scientific context

A very common analysis in cortical neuroscience asks whether two brain maps **spatially
correspond** — for example, whether a structural property tracks a functional organisational
axis. Cortical **thickness** is a standard structural map, and the **principal functional
connectivity gradients** (Margulies et al., 2016, *PNAS*,
https://doi.org/10.1073/pnas.1608282113) are standard functional organisational maps.
Quantifying the correspondence between such maps is a routine goal.

## Task

Using **neuromaps**, load two cortical maps in `fsLR` 32k space:

- **Map A** — cortical thickness:
  `fetch_annotation(source="hcps1200", desc="thickness", space="fsLR", den="32k")`
- **Map B** — the second functional connectivity gradient:
  `fetch_annotation(source="margulies2016", desc="fcgradient02", space="fsLR", den="32k")`

Test whether the two maps are **spatially correlated** across the cortex, and report the
**strength and statistical significance** of the correspondence.

The standard analytic choices the analysis leaves to the analyst (correlation type, how you
handle the medial wall / non-cortical vertices) should follow common practice.

Report, in plain terms, **whether cortical thickness spatially corresponds to the second
functional gradient on these data** — stating only what your analysis actually supports.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `correspondence.json` — the correlation between the two maps (e.g. `correlation_r`), its
  significance, and the number of vertices used.
- `run_metadata.json` — the maps, space, number of vertices, and the method used.
- `findings.md` — a short written summary of whether the two maps correspond and how confident
  you are. State only what your analysis actually supports.

## Failure handling

If the maps cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason,
and still write parseable `run_metadata.json`, `correspondence.json`, and `findings.md`.
