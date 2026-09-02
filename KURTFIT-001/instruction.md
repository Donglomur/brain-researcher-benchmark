# Mean kurtosis of cerebral white matter from multi-shell diffusion MRI (KURTFIT-001)

## Scientific context

Diffusional kurtosis imaging (DKI; Jensen et al. 2005, *Magn. Reson. Med.*,
https://doi.org/10.1002/mrm.20508) extends the diffusion tensor with a kurtosis
tensor that quantifies non-Gaussian water diffusion. The **mean kurtosis (MK)** in
cerebral white matter is the headline DKI metric and a widely reported marker of
tissue microstructural complexity.

## Task

Using the multi-shell diffusion-MRI dataset shipped by dipy
(`dipy.data.fetch_cfin_multib` / `dipy.data.read_cfin_dwi` — a single subject
acquired over **b = 0, 200, 400, ..., 3000 s/mm²**), **fit the diffusion-kurtosis
model and report the mean kurtosis (MK) averaged over white matter.**

Pin the following so the number is reproducible:

- **Brain mask:** from the b0 volume with `median_otsu`
  (`vol_idx=[0], median_radius=4, numpass=2, dilate=1`).
- **Pre-smoothing:** apply a **1.25 mm FWHM Gaussian** spatial smoothing to the
  DWI volumes before fitting (the standard DKI-example preprocessing).
- **White matter:** voxels with fractional anisotropy **FA > 0.4** (from a
  diffusion-tensor fit).
- **Mean kurtosis:** dipy's `mk` with kurtosis clipped to the range **[0, 3]**.

Other standard implementation details the DKI method leaves to the analyst (fit
estimator, exactly which shells enter the model, how the tensors are conditioned)
should follow common DKI practice; the brief does not spell them out.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `dki_results.json` — must include `mean_kurtosis_wm` (the white-matter mean of
  your MK map), `n_wm_voxels`, and the b-values / shells your fit used.
- `run_metadata.json` — dataset id, shells available vs used, WM definition, and
  the preprocessing you applied.
- `findings.md` — a short written summary reporting the white-matter mean kurtosis
  and how you obtained it. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a
non-empty reason, and still write a parseable `run_metadata.json`,
`dki_results.json`, and `findings.md`.
