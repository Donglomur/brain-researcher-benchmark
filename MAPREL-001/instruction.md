# Relating a functional connectivity gradient to cortical thickness (MAPREL-001)

## Scientific context

Macroscale **gradients** of functional connectivity (Margulies et al. 2016, *PNAS*)
and structural properties of the cortex such as **cortical thickness** each vary
smoothly across the cortical sheet. A recurring question in cortical neuroscience is
whether a given functional gradient spatially tracks a structural property — i.e.
whether the two maps are *spatially correlated* across the cortex. Here you assess the
spatial correspondence between the **second** macroscale functional-connectivity
gradient and the group-average **cortical-thickness** map.

## Task

Using `neuromaps`, obtain two published cortical surface maps, both in `fsLR` `32k`
space (so no resampling is needed):

- **Map A** — the second macroscale functional-connectivity gradient:
  `neuromaps.datasets.fetch_annotation(source="margulies2016", desc="fcgradient02", space="fsLR", den="32k")`.
- **Map B** — the group-average cortical-thickness map (HCP S1200):
  `neuromaps.datasets.fetch_annotation(source="hcps1200", desc="thickness", space="fsLR", den="32k")`.

Parcellate both maps with the **Schaefer-2018 400-parcel, 7-network** atlas in `fsLR`
`32k` (the dense `.dlabel.nii`, in which the medial wall is label `0` and is excluded),
taking the **mean map value within each of the 400 parcels**. The Schaefer `fsLR` `32k`
dlabel is available from the `ThomasYeoLab/CBIG` repository
(`.../Schaefer2018_LocalGlobal/Parcellations/HCP/fslr32k/cifti/Schaefer2018_400Parcels_7Networks_order.dlabel.nii`).

Then quantify the spatial correspondence between the two parcellated maps: compute the
**Pearson correlation across the 400 parcels**, and determine **whether the two maps
are significantly spatially correlated across the cortex**.

Report the correlation and its statistical significance, stating only what your analysis
actually supports.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `parcels.csv` — one row per parcel:
  `parcel_id, network, gradient2, thickness` (the parcel-mean value of each map).
- `results.json` — at least `n_parcels`, the Pearson `r`, and the p-value(s) /
  significance you determined for the association.
- `run_metadata.json` — the map sources, space, parcellation, and the analysis choices
  you made.
- `findings.md` — a short written summary stating whether the second functional
  gradient and cortical thickness are significantly spatially correlated on these data,
  and the basis for that judgement. State only what your analysis actually supports.

## Failure handling

If the maps or the parcellation cannot be resolved, exit non-zero with
`failed_precondition` and a non-empty reason, and still write parseable
`run_metadata.json`, `results.json`, and `findings.md`.
