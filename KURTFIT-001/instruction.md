# White-matter mean-kurtosis shell sensitivity (KURTFIT-001)

## Scientific target and data

Reproduce a declared diffusion-kurtosis imaging (DKI) **method-sensitivity
baseline** on the public CFIN multi-shell acquisition. Compare mean kurtosis
(MK) across b-value caps on one fixed FA-defined white-matter ROI.

DKI follows [Jensen et al. (2005)](https://doi.org/10.1002/mrm.20508).
The data are associated with [Hansen and Jespersen (2016)](https://doi.org/10.1038/sdata.2016.72),
*Data for evaluation of fast kurtosis strategies, b-value optimization and
exploration of diffusion MRI contrast*, and the
[UW ResearchWorks deposit](https://digital.lib.washington.edu/handle/1773/38488).
This is one acquisition and a task-defined estimator comparison, not a numerical
reproduction of Jensen's original cohort or a claim that one b-cap is biological
ground truth. No particular direction or minimum size of sensitivity is required.

Three original files (NIfTI, b-values, b-vectors) are already available at
`/app/data/cfin`. Their exact names, roles, byte counts and checksums are in
`/app/data/cfin/data_manifest.json`. Use those bytes without a runtime download.
The image has shape 96 × 96 × 19 × 496, millimeter spatial units, a b0 volume
followed by diffusion volumes, and shells from 200 to 3000 s/mm².

## Public estimation contract

Use DIPY 1.12.1 (installed), or an implementation numerically equivalent to the
following baseline. These choices define this comparison; they are not a unique
scientifically valid DKI pipeline.

1. Read the image in float64 without reorientation/resampling. Preserve original
   voxel coordinates and gradient-volume alignment. Set gradient `b0_threshold=50`.
2. Derive the brain mask from the **original unsmoothed b0** with
   `median_otsu(vol_idx=[0], median_radius=4, numpass=2, autocrop=False, dilate=1)`.
3. Smooth each original DWI volume spatially using a Gaussian of **1.25 mm FWHM**:
   `sigma_xyz = 1.25 / (sqrt(8*log(2)) * header_voxel_sizes_mm)`.
   Use `scipy.ndimage.gaussian_filter`, `mode="reflect"`, `truncate=4`, and zero
   sigma on the volume axis. This width is a task choice, not a claimed paper
   preprocessing recipe.
4. Fit a diffusion tensor with `TensorModel(..., fit_method="WLS", min_signal=0.0001)`
   to smoothed brain voxels using source volumes with `bvals <= 2000 + 50`.
   Define the **fixed ROI** as brain-mask voxels with finite FA and **FA > 0.4**.
   Do not redefine the ROI using MK, or separately for different shell caps.
5. Evaluate at least two distinct caps from **1000, 1400, 2000, 2400, 3000 s/mm²**,
   including **2000**. For cap c use every source volume with `bvals <= c + 50`;
   report the actual highest included b-value c, not a nonexistent 2500 shell.
6. For each cap fit `DiffusionKurtosisModel(..., fit_method="WLS",
   min_signal=0.0001, return_S0_hat=True)` on the same fixed ROI.
   Compute `fit.mk(min_kurtosis=0, max_kurtosis=3, analytical=True, fast=True)`.
   WLS is the pinned DIPY two-step log-signal fit (OLS-derived predicted-signal
   weights followed by weighted least squares), not OLS or a constrained fit.
   Retain every fixed-ROI voxel; nonfinite values are an error, not a reason to
   silently discard rows. The **primary map and headline mean use cap 2000**.

## Outputs

Write files to `${OUTPUT_DIR}` (default `/app/output`).

- `mk_voxelwise.csv`: columns `i,j,k,mk`; exactly one row per fixed-ROI voxel
  from the cap-2000 fit.
- `mk_sweep.csv`: columns `i,j,k,max_b,mk`; exactly one row per fixed-ROI voxel
  for **every submitted cap**. No duplicate or extra coordinates. CSV row order,
  additional columns and equivalent numeric representations do not matter.
- `dki_results.json`: `status: "ok"`, `pipeline_id: "cfin-physical-wls-v2"`,
  `mean_kurtosis_wm`, `n_wm_voxels`, `b_max_used: 2000`, `shells_used`
  (sorted unique primary b-values), `mean_kurtosis_wm_by_bcap` (object keyed by
  the submitted caps as strings), and `mk_shell_cap_spread` (maximum minus
  minimum of those submitted ROI means). Means/counts must recompute from CSVs.
- `run_metadata.json`: source and estimator receipt with the following fields.
  Derived geometry and volume arrays must come from the actual source, not from
  invented values. Describe all five **available** subsets even if fitting only
  two; this declaration is not a requirement to fit the unused subsets.

```text
pipeline_id: "cfin-physical-wls-v2"
dataset_id: "cfin-multib"
source_sha256: {original_filename: sha256, ...}  # all three source files
shape: [96, 96, 19, 496]
affine: <source 4x4 affine>
voxel_sizes_mm: <three header zooms>
spatial_units: "mm"
preprocessing:
  brain_mask: {vol_idx: [0], median_radius: 4, numpass: 2, autocrop: false, dilate: 1}
  fwhm_mm: 1.25
  sigma_vox: [<sigma_x>, <sigma_y>, <sigma_z>, 0]
  mode: "reflect"
  truncate: 4
roi:
  method: "DTI-WLS"
  max_b: 2000
  selection_tolerance: 50
  fa_threshold: 0.4
  min_signal: 0.0001
  finite_fa_required: true
dki:
  fit_method: "WLS"
  min_signal: 0.0001
  return_S0_hat: true
  mk_clip: [0, 3]
  analytical: true
  fast: true
  dipy_version: "1.12.1"
gradient_b0_threshold: 50
primary_cap: 2000
available_caps: [1000, 1400, 2000, 2400, 3000]
shell_subsets:
  "<cap>": {volume_indices: <zero-based indices>, bvals: <b-value per selected volume>,
            shells: <sorted unique selected b-values>, max_b: <cap>}
```

- `findings.md`: summarize the measured primary MK, ROI size and shell-cap
  sensitivity. Explain limitations of a single acquisition, FA-based tissue
  selection, clipping and estimator dependence. Finite clipped MK is not evidence
  of a stable fit: inspect clipping and signal residuals before interpreting it
  as tissue physiology. You may retain additional fit/QC diagnostics; do not
  silently change the fixed ROI to hide failed fits. No required English phrases.

Scoring is **all-or-nothing**, not proportional. Every submitted map is compared
with the declared cap's source-derived baseline (absolute MK tolerance 1e-5).
Internal CSV/JSON arithmetic and primary-to-sweep agreement use absolute tolerance
1e-6. Affine, voxel sizes and sigma metadata may be rounded to six decimal places
(absolute tolerance 1e-6). No correlation-only substitute, required trend or
minimum spread is used. This is a reproducible method control, not an unannounced
test of choosing the reference author's preferred estimator.

If a source or numerical precondition fails, exit nonzero and write parseable
`run_metadata.json`, `dki_results.json` and `findings.md` with
`status: "failed_precondition"` and a nonempty reason; such a run is not a pass.
