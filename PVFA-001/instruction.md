# Diffusion-model sensitivity in a diffusion-defined proxy ROI

Compare model-derived FA estimates on one original Sherbrooke diffusion scan.
Use any two or all three public recipes below and designate one as your main
model. This is a paper-derived method case, not a reproduction of an original
cohort finding or an independently validated estimate of tissue microstructure.

## Data and scientific scope

The original image/b-values and documented upstream orientation-corrected
b-vectors are under `/app/data/sherbrooke`. Verify `data_manifest.json` and its
checksums. The bundle has one b0 and 64 directions each at b=1000, 2000 and
3500 s/mm². Do not apply another gradient flip or reorient the image. Inputs
are CC0 and runtime is offline. Original source:
https://digital.lib.washington.edu/researchworks/handle/1773/38475.

The two-compartment signal model is
`S = S0 * [(1-f)*exp(-b*gᵀDg) + f*exp(-b*0.003)]`.
Its method connection is Hoy et al. (2014),
https://doi.org/10.1016/j.neuroimage.2014.09.053, and Henriques et al. (2017),
Eq. 1 and WLS/NLS methods, https://doi.org/10.5281/zenodo.495237.
This Sherbrooke acquisition is not those papers' original analysis cohort.
Conventional tensor FA and two-compartment tissue-tensor FA are different
model summaries; neither supplies independent ground truth for the other.

## Public preprocessing and ROI

Complete numerical settings, source identities and library versions are in
`/app/method_contract.json`. Use that recipe or a numerically equivalent
implementation. The provided stack is DIPY 1.12.1, NumPy 2.1.3 and SciPy 1.14.1.

1. Construct the brain mask from the original unsmoothed b0 with `median_otsu`:
   median radius 4, two passes, dilation 1, no cropping.
2. Smooth each volume used for ROI construction or fitting spatially in float64:
   Gaussian FWHM **0.625 voxels**,
   sigma `0.625/sqrt(8*log(2))`, `mode="reflect"`, `truncate=4`. Do not smooth
   across volumes. Unused b=3500 volumes need not be smoothed. The NIfTI header
   does not declare spatial units; do not label
   this kernel as a verified physical-mm length.
3. Fit the low-b WLS tensor (b0+1000) in the brain mask. Seed every in-brain
   voxel with MD>0.002 mm²/s and FA<0.2. Dilate this seed by two iterations of
   six-neighbor binary dilation, remove the seed, and retain in-brain voxels
   with 0.0008<MD<0.0015 mm²/s and FA>0.25.

This is a diffusion-defined high-MD/low-FA-adjacent tissue **proxy**, not an
anatomical ventricular or white-matter segmentation. Preserve every resulting
voxel in the acquisition's zero-based i,j,k coordinates. Only an empty ROI is
a precondition failure; do not tune thresholds to obtain a desired count.

## Accepted model recipes

- `dti_b1000`: b0+1000 two-pass WLS. Floor signal at 1e-4 for logs; use OLS
  predicted-signal weights, pseudoinverse cutoff 1e-15, and the public DIPY
  eigenvalue floor `1e-6/(-design.min())`. Retain raw tensor coefficients and
  fitted negative-log S0 before eigenvalue flooring.
- `dti_b2000`: the same recipe with b0+1000+2000.
- `fwdti`: b0+1000+2000, instrumented DIPY WLS initialization and signal-space
  Levenberg–Marquardt fit. Isotropic diffusivity is 0.003 mm²/s. Initialization
  uses observed-signal-squared weights, minimum signal 1e-6, MD boundary 0.0027,
  and the public 9/19/19 fraction grids. NLS starts from the initialized tensor,
  negative log observed b0, and `asin(2*f_init-1)+pi/2`. The fraction transform
  is `f=(1+sin(ft-pi/2))/2`; no Cholesky transform, analytic fit Jacobian,
  extra weighting or tensor/S0 box bounds are used. `leastsq` settings are
  ftol=xtol=1.49012e-8, gtol=0, maxfev=1800, epsfcn=None, factor=100, diag=None.
  Retain the actual fitted S0 and raw tensor, not only clipped eigenvalues/FA.

The template defines the exact initialization and failure branches. In
particular, low-signal/MD sentinels, an initial fraction>=0.99 that skips NLS,
or exhausted/failed optimization are not converged tissue fits. Successful NLS
termination codes are 1–4. Do not silently substitute the initializer after a
failed decomposition. Numerical warnings and convergence/identifiability
limitations should be reported, not suppressed as evidence of success.

For every candidate, compute predictions and SSE from its **raw** tensor,
actual fitted S0 and fraction against the unfloored, smoothed source signal.
`nrmse=sqrt(SSE/n_volumes)/max(observed_b0,1e-6)`. Reported FA/MD use the
declared eigenvalue flooring (zero for fwdti); record how many eigenvalues
changed. Clipped FA is a computational summary, not proof of a physical tensor.

Keep every model×ROI row, including skipped and failed fits. An eligible row
requires a successful finite fit/prediction, positive fitted S0, a nonzero
reported tensor and 0<=f<1. Preserve finite failed candidates but mark them
ineligible. Unattempted final parameters/metrics are blank, not zero estimates.
`init_md` is the preliminary observed-weighted WLS MD used for initialization's
MD check. Fraction boundary flags at <=1e-6 and >=1-1e-6 are diagnostic only.
Do not add a residual, rank or physiological exclusion after inspecting results.

Report each model's eligible-row means. Also intersect eligibility across the
**selected** models and compute their paired FA differences on that common
support. Empty-support means/differences are JSON null. No free-water model,
effect direction, minimum gap, particular valid count or prose keywords are
required. The two single-tensor models alone are an acceptable pair.

## Required outputs

Write to `${OUTPUT_DIR}` (default `/app/output`). CSV rows/columns may be
reordered. Every required identity must appear exactly once; extra descriptive
columns are allowed. Retain adequate precision.

- `fa_voxelwise.csv`: `i,j,k,fa` for every ROI voxel under the main model.
- `fa_sweep.csv`: `i,j,k,model,fa` for every selected model×ROI voxel.
- `fit_parameters.csv`: complete model×ROI rows with
  `i,j,k,model,status,fit_attempted,eligible,common_valid,Dxx,Dxy,Dyy,Dxz,Dyz,Dzz,`
  `neg_log_S0,S0_hat,f,fa,md,sse,nrmse,n_eigenvalues_clipped,optimizer_status,nfev,`
  `init_f,init_md,n_signal_floored,observed_b0,normalization_scale,`
  `boundary_f_low,boundary_f_high`.
  DTI has f=0, blank optimizer_status and nfev=0. Status is one of `ok`,
  `invalid_input`, `insufficient_signal`, `md_threshold`, `initialization_failed`,
  `high_initial_fraction`, `optimizer_failed`, `nonfinite_candidate`,
  `decomposition_failed`. The FA tables reflect available candidate FA, even
  for finite failed candidates; headline means use eligible rows only.
- `results.json`: `status:"ok"`, `pipeline_id:"sherbrooke-proxy-fa-v2"`,
  `main_model,n_roi_voxels,n_common_valid,fa_proxy_roi,by_model,common_valid`.
  `fa_proxy_roi` is the main model's own eligible-row mean.
  `by_model[model]` contains `n_valid,fa_mean,md_mean,f_mean,S0_hat_mean,nrmse_mean,`
  `status_counts,n_eigenvalues_clipped_total,n_voxels_eigenvalues_clipped`.
  Zero-count statuses may be included or omitted in status-count dictionaries.
  `common_valid` contains `n_voxels`, `by_model` with the same five means on
  common support, and `paired_fa_differences`. For each lexicographically sorted
  selected pair left/right, name the contrast `right_minus_left` and average
  rightFA-leftFA on common support.
- `run_metadata.json`: the public template plus `status:"ok"`, `main_model`,
  `fitted_models,n_roi_voxels,n_brain_voxels,n_seed_voxels,n_common_valid,`
  `status_counts_by_model`.
- `findings.md`: a numerical comparison with support counts and fit limitations.
  Do not interpret a higher fitted FA as independently demonstrated tissue
  recovery, an isotropic signal fraction as measured CSF volume, or the proxy
  mask as validated periventricular anatomy.

The verifier checks the complete source-defined ROI, model-bound raw parameters,
signal predictions, residuals, clipped metrics and recomputed summaries. Public
tolerances include tensor coefficients atol1e-8/rtol1e-5, f/FA atol/rtol1e-5,
S0 normalized by the declared scale atol/rtol1e-5, normalized predictions
atol1e-5, residual arithmetic1e-6, and MD arithmetic atol1e-8/rtol1e-6.
Identities, model selection and coverage
are exact. Eigenvector signs, the periodic ft parameter, optimizer messages and
exact evaluation counts are not point-matched. Scoring is all-or-nothing.
Authoring-only arrays are not required participant outputs.
Within-row algebra (including S0 from the retained intercept), cross-file
consistency and recomputed summaries use atol=rtol=1e-6. Normalized source
prediction matching uses absolute tolerance 1e-5 with no relative component.

If source verification or required preprocessing fails, exit nonzero with
parseable results/metadata carrying `status:"failed_precondition"`, a nonempty
reason and findings. Do not fabricate missing observations or drop troublesome
ROI coordinates to obtain a passing summary.
