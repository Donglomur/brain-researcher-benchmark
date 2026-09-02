# Crossing-fibre fraction in the centrum semiovale (FODCROSS-001)

## Scientific context

Spherical-deconvolution estimation of the fibre orientation distribution (fODF)
resolves multiple intra-voxel fibre populations, and the fraction of white-matter
voxels that contain a *crossing* (two or more distinct fODF peaks) is a standard
summary of the multi-fibre structure of a white-matter region (Tournier et al. 2007;
Jeurissen et al. 2013, *Human Brain Mapping*, https://doi.org/10.1002/hbm.22099, on the
prevalence of complex fibre configurations). The **centrum semiovale** — where the corpus
callosum, corticospinal tract and superior longitudinal fasciculus interdigitate — is the
textbook site of crossing fibres.

## Task

Using dipy's pinned multi-shell diffusion MRI phantom-subject acquisition
`sherbrooke_3shell` (`dipy.data.fetch_sherbrooke_3shell` / `read_sherbrooke_3shell`;
b = 0, 1000, 2000, 3500 s/mm^2), **estimate the fibre orientation distribution (fODF)
by spherical deconvolution and report the fraction of white-matter voxels in the
centrum-semiovale ROI defined below whose fODF contains a crossing (>= 2 peaks).**

Pin the measurement exactly as follows so the crossing fraction is well defined; the
only thing left to your judgement is how the fODF itself is estimated from this
acquisition.

### Region of interest (fixed)

- Brain mask: `dipy.segment.mask.median_otsu` on the mean b0 volume
  (`median_radius=3, numpass=1`).
- Fit a diffusion tensor (`dipy.reconst.dti.TensorModel`) on the b=0 and b=1000 shells
  only, and take its fractional anisotropy (FA).
- ROI = the voxel box `data[45:83, 45:90, 31:36]` (a superior axial slab through the
  centrum semiovale) intersected with the brain mask and with `0.30 < FA < 0.90`.

### Peak / crossing definition (fixed)

- Extract fODF peaks with `dipy.direction.peaks_from_model` on
  `dipy.data.default_sphere`, with `relative_peak_threshold=0.5`,
  `min_separation_angle=25`, `npeaks=3`.
- A voxel is a **crossing** voxel if it has `>= 2` peaks with positive peak value.
- Report the crossing fraction = (crossing voxels) / (all ROI voxels), a number in [0, 1].

Use `sh_order_max=8` for the deconvolution. Every other implementation choice the
spherical-deconvolution literature leaves to the analyst should follow common practice.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `crossing.json` — at minimum `{"crossing_fraction": <float>, "n_roi_voxels": <int>,
  "n_crossing_voxels": <int>}`.
- `run_metadata.json` — dataset id, the fODF estimation method you used, `sh_order_max`,
  and the peak parameters.
- `findings.md` — a few sentences reporting the crossing fraction in the centrum-semiovale
  ROI and how you estimated the fODF. State only what your analysis supports.

## Failure handling

If the `sherbrooke_3shell` acquisition cannot be resolved, exit non-zero with
`failed_precondition` and a non-empty reason, and still write a parseable
`run_metadata.json`, `crossing.json`, and `findings.md`.
