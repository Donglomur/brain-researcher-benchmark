# Inter-subject synchrony of the movie response in visual cortex (MOVIESYNC-001)

## Scientific context

When people watch the same movie, their sensory cortices respond in a stimulus-locked way,
so the evoked BOLD time courses are correlated *across* individuals. This **inter-subject
correlation (ISC)** is a standard measure of how reliably a naturalistic stimulus drives a
region, and it is strongest in early sensory cortex (Hasson et al. 2004). The nilearn
`development_fmri` release (OpenNeuro `ds000228`, Richardson et al. 2018) provides
preprocessed BOLD from participants who all watched the same Pixar short film,
*Partly Cloudy*.

## Task

Using the nilearn development dataset, **measure the inter-subject correlation of the
movie-evoked response in visual cortex and report it.**

Fetch the data with

```python
from nilearn.datasets import fetch_development_fmri, fetch_atlas_msdl
dev  = fetch_development_fmri(n_subjects=40)   # dev.func, dev.confounds
msdl = fetch_atlas_msdl()                      # atlas maps + region labels
```

Pin the analysis as follows so the number is comparable:

- **Participants:** the 40 returned by `fetch_development_fmri(n_subjects=40)`.
- **Regions:** the three visual-cortex regions of the **MSDL** atlas, labelled
  `"Vis"`, `"Striate"` and `"Occ post"`.
- **Time series:** extract each participant's region time series with
  `nilearn.maskers.NiftiMapsMasker(maps_img=msdl.maps, standardize="zscore_sample",
  low_pass=0.1, high_pass=0.01, t_r=2.0)`, passing that participant's `confounds` file so
  nuisance signals are regressed out. Truncate all participants to the common number of
  time points.
- **Quantity:** the **inter-subject correlation** of the movie time course in each of the
  three visual regions, averaged over the three regions. Report a single headline value
  (chance ≈ 0).

Report the inter-subject correlation of the visual-cortex movie response.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `isc_results.json` — at least a field `visual_isc` (float), the inter-subject correlation
  you obtained for visual cortex, plus `n_subjects`, `n_timepoints` and `chance`.
- `run_metadata.json` — dataset id, atlas, regions, preprocessing and how you estimated the
  inter-subject correlation.
- `findings.md` — a short written summary stating the inter-subject correlation of the
  visual-cortex movie response and how you computed it. State only what your analysis
  actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `isc_results.json`, and `findings.md`.
