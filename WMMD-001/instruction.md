# Conditional white-matter diffusivity on CFIN (WMMD-001)

Estimate mean diffusivity (MD) and fractional anisotropy (FA) on one public human
diffusion acquisition, using **one** of the three specified model configurations.
This is a paper-derived method control, not reproduction of an unbiased biological
quantity or a population finding. Rotational invariance does not make MD independent
of model, shell range, noise or preprocessing.

## Data and scientific scope

The original CFIN image and gradients are staged under `/app/data/cfin`; the
`data_manifest.json` records their sizes, hashes, URLs and CC0 source. No network
is needed. There are 496 volumes, one b0 at index 0 and 33 directions at each
b=200,400,...,3000 s/mm²; the human acquisition used inversion-recovery CSF
suppression. Use the unsmoothed source values and native voxel geometry.
The dataset is described by Hansen & Jespersen (2016),
https://doi.org/10.1038/sdata.2016.72.

Jensen & Helpern (2010), https://doi.org/10.1002/nbm.1518, motivates the
diffusion/kurtosis signal expansion. Veraart et al. (2011),
https://doi.org/10.1002/mrm.22603, motivates model-dependent tensor estimation:
its rat/Rician-estimation result is **not** the human log-WLS analysis requested
here. No independent diffusivity truth is supplied.

## Public estimator contract

The full metadata templates for all choices are in `/app/method_contract.json`.
Choose `dki_all` (DKI, all 496 volumes), `dti_lowb` (DTI, 166 volumes with
`round(bvals,-2)<=1000`), or `dti_all` (DTI, all 496 volumes). All three are
valid conditional estimators here. You need not compute or compare the other two.

1. Brain mask: DIPY 1.12.1 `median_otsu`, `vol_idx=[0]`,
   `median_radius=4`, `numpass=2`, `autocrop=False`, `dilate=1`.
2. Define a common ROI by low-b DTI-WLS on that brain mask, with
   `min_signal=1e-4`: keep every voxel with finite FA strictly greater than 0.5.
   Use `gradient_table(..., b0_threshold=50, atol=0.01)`.
   Do not add exclusions, smooth data or rescale signal.
3. For your selected configuration use the DIPY 1.12.1 DTI/DKI design matrix
   `A`. Its first six columns encode
   `Dxx,Dxy,Dyy,Dxz,Dyz,Dzz`; its final column is -1, so the final coefficient
   is `-log(S0)`. DKI's intervening 15 columns encode dimensionful quartic
   coefficients, not normalized kurtosis. Their exact order is in the template.
4. On each voxel fit two-pass WLS:
   `y=log(max(raw_signal,1e-4))`,
   `beta_OLS=pinv(A,rcond=1e-15)@y`,
   `w=exp(A@beta_OLS)`,
   `beta=pinv(w[:,None]*A,rcond=1e-15)@(w*y)`.
   Keep these **raw** coefficients as the fit receipt.
5. Diagonalize the raw diffusion tensor and floor **each** eigenvalue at
   `1e-6/(-A.min())`, as in the pinned baseline. Compute MD and FA from these
   floored eigenvalues. For signal prediction, replace only the first six
   coefficients with the reconstructed floored tensor; retain raw quartic
   coefficients and intercept. Predict `exp(A@beta_postfloor)`.
6. Report `S0_hat=exp(-beta[-1])`, not a default S0 of 1.
   `observed_b0` is the mean raw b0 signal (one volume here);
   `normalization_scale=max(observed_b0,1e-4)`.
   `nrmse` is RMSE of the predicted versus **raw** selected signal divided by
   that scale. `log_rmse` uses `y-A@beta` before eigenvalue flooring.
   Count selected samples below the signal floor and raw eigenvalues below the
   eigenvalue floor. Keep every ROI voxel, including poorly fitting ones.
   These diagnostics are not physiological acceptance thresholds.

Equivalent numerical implementations of this public estimator are welcome.
The exact complete ROI, model declaration and units are checked; rows may be
reordered. No correlation-only test, hidden MD band or preferred model is used.
Numeric tolerances: raw diffusion coefficients atol 1e-10, quartic coefficients
1e-12, intercept 1e-7 (all rtol 1e-6); MD/FA/residuals atol/rtol 1e-6;
S0 divided by normalization scale atol/rtol 1e-6; normalized predictions
atol 1e-5, rtol 1e-6. Do not round coefficients aggressively.

## Outputs

Write to `${OUTPUT_DIR}` (default `/app/output`).

- `md_voxelwise.csv`: exactly one row per ROI voxel, integer `i,j,k`, followed
  by `md,fa,S0_hat,observed_b0,normalization_scale,nrmse,log_rmse,
  n_signal_floored,n_eigenvalues_floored` and `beta_0,...,beta_(P-1)`;
  P=22 for DKI and 7 for DTI. All numeric values must be finite.
  MD is in `1e-3 mm^2/s`; FA is dimensionless. Raw diffusion coefficients
  remain in mm²/s and quartic coefficients in mm⁴/s².
- `diffusivity.json`: `status:"ok"`,
  `pipeline_id:"cfin-unsmoothed-wls-md-fa-v2"`, selected `model_config`,
  `md_units:"1e-3 mm^2/s"`, `n_wm_voxels`, and arithmetic voxel means
  `md_mean,fa_mean,S0_hat_mean,nrmse_mean,log_rmse_mean`.
  Include `n_signal_floored_total,n_eigenvalues_floored_total,
  n_voxels_signal_floored,n_voxels_eigenvalues_floored`, recomputed from your rows.
- `run_metadata.json`: the selected object from `method_contract.json`,
  plus `status:"ok"`, `n_wm_voxels` and `n_brain_voxels`.
- `findings.md`: briefly state the selected model, estimates, residual/flooring
  diagnostics and limitations. ROI selection depends on low-b FA; one scan and
  log-WLS do not establish unbiasedness, generalization or physiological truth.
  Do not assert an uncomputed model comparison.

Scoring is all-or-nothing; no proportional-scoring claim is made. Quantitative
grading does not use prose keywords. The authoring-only reference archive is
not a required participant output.

If source verification or a required finite fit fails, exit nonzero and write
parseable `run_metadata.json` and `diffusivity.json` with
`status:"failed_precondition"` and a nonempty reason, plus `findings.md`.
Do not invent or drop measurements to obtain a passing result.
