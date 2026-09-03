# White-matter mean diffusivity from a multi-b diffusion acquisition (WMMD-001)

## Scientific context

Mean diffusivity (MD) and fractional anisotropy (FA) are the standard rotationally
invariant summaries of the water-diffusion signal in a white-matter region. MD (the
average of the diffusion-tensor eigenvalues) is a convention-invariant physical quantity
with units of mm^2/s, independent of any fibre-orientation convention. This task asks you
to report the mean MD and FA over a fixed white-matter ROI from a single subject's
diffusion MRI acquisition.

## Task

Using dipy's pinned `cfin_multib` diffusion acquisition
(`dipy.data.read_cfin_dwi`; b-values 0, 200, 400, ..., 3000 s/mm^2), **estimate the
white-matter mean diffusivity (MD) and fractional anisotropy (FA) over the region of
interest defined below, and report the ROI-mean MD and ROI-mean FA.**

The ROI is pinned exactly so the reported means are well defined; the only thing left to
your judgement is **how you model the diffusion signal from this acquisition** to obtain
MD and FA.

### Region of interest (fixed)

- Brain mask: `dipy.segment.mask.median_otsu` on the acquisition with
  `vol_idx=[0], median_radius=4, numpass=2, dilate=1`.
- Reference FA for the ROI: fit a diffusion tensor
  (`dipy.reconst.dti.TensorModel`) on the **b <= 1000** shells only and take its FA.
- ROI = the brain mask intersected with (reference FA > 0.5). This is the white-matter
  ROI over which you report the means (about 1x10^4 voxels).

Use this exact ROI. The reference-FA tensor above only *defines* the ROI; you must still
decide for yourself how to estimate the MD and FA that you report over it.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `diffusivity.json` — at minimum
  `{"md_mean": <float>, "fa_mean": <float>, "md_units": "1e-3 mm^2/s", "n_wm_voxels": <int>}`.
  **Report `md_mean` in units of 1e-3 mm^2/s (i.e. um^2/ms)** — a white-matter MD is of
  order 0.8 in these units. `fa_mean` is dimensionless in [0, 1].
- `run_metadata.json` — dataset id, the diffusion model / estimation method you used, and
  the ROI voxel count.
- `findings.md` — a few sentences reporting the ROI-mean MD and FA and how you estimated
  them. State only what your analysis supports.

## Failure handling

If the `cfin_multib` acquisition cannot be resolved, exit non-zero with
`failed_precondition` and a non-empty reason, and still write a parseable
`run_metadata.json`, `diffusivity.json`, and `findings.md`.
