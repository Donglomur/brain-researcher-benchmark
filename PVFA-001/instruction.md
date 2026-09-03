# Fractional anisotropy of periventricular white matter (PVFA-001)

## Scientific context

Fractional anisotropy (FA) from diffusion MRI is the most widely reported marker
of white-matter microstructure. White matter that borders the lateral ventricles
(periventricular white matter — e.g. the margins of the corpus callosum, the
corona radiata, the fornix) is a routine target in studies of ageing, small-vessel
disease, hydrocephalus and multiple sclerosis, and its FA is a standard summary
measure (Metzler-Baddeley et al. 2012, *NeuroImage*).

## Task

Using the multi-shell diffusion-MRI dataset shipped by dipy
(`dipy.data.read_sherbrooke_3shell` / `fetch_sherbrooke_3shell` — a single subject
acquired at **b = 0, 1000, 2000 and 3500 s/mm²**), **estimate the fractional
anisotropy of periventricular white matter and report its mean over the region
defined below.**

Pin the following so the number is reproducible:

- **Brain mask:** from the b0 volume with `median_otsu`
  (`vol_idx=[0], median_radius=4, numpass=2, dilate=1`).
- **Pre-smoothing:** apply a **1.25 mm FWHM Gaussian** spatial smoothing to the
  DWI volumes before any fitting.
- **Reference FA/MD maps (for locating the region):** fit a standard diffusion
  tensor to the **b ≤ 1000** shells (b0 + b=1000) and take its FA and MD maps.
- **CSF seed:** brain voxels with **MD > 2.0×10⁻³ mm²/s and FA < 0.2** (the
  ventricular cerebrospinal fluid).
- **Periventricular white-matter region:** dilate the CSF seed by **2 iterations**
  with `scipy.ndimage.binary_dilation` (its default structuring element — first-order
  / 6-neighbour connectivity), remove the CSF seed itself, and keep the voxels that
  are inside the brain mask with
  **0.8×10⁻³ < MD < 1.5×10⁻³ mm²/s and FA > 0.25**. This is the region of interest.
- **Model estimation:** estimate the diffusion tensor / model on the **b = 0, 1000
  and 2000** shells (the b = 3500 shell is too heavily diffusion-weighted for
  tensor estimation and is excluded).

Other standard implementation details the analysis leaves to the analyst (the exact
tensor estimator, how the model is conditioned) should follow common diffusion-MRI
practice; the brief does not spell them out.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `results.json` — must include `fa_periventricular_wm` (your mean FA over the
  region above), `n_roi_voxels`, and the shells your estimate used.
- `run_metadata.json` — dataset id, shells available vs used, the region
  definition, and the preprocessing you applied.
- `findings.md` — a short written summary reporting the periventricular
  white-matter FA and how you obtained it. State only what your analysis actually
  supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a
non-empty reason, and still write a parseable `run_metadata.json`, `results.json`,
and `findings.md`.
