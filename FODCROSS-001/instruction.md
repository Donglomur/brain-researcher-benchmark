# Crossing-peak sensitivity to fODF reconstruction (FODCROSS-001)

## Scientific target

Compare spherical-deconvolution estimates of the fraction of voxels with two or
more fODF peaks, using one fixed ROI in the public Sherbrooke three-shell scan.

The method context is [Jeurissen et al. (2014)](https://doi.org/10.1016/j.neuroimage.2014.07.061),
*Multi-tissue constrained spherical deconvolution for improved analysis of
multi-shell diffusion MRI data*. This is a **paper-derived method control**,
not a numerical reproduction of that paper's cohort or a measurement of true
population crossing-fibre prevalence. The fixed voxel box below is an operational
slab, not an independently segmented anatomical structure. Estimator disagreement
does not establish which reconstruction is biologically correct.

The original image/b-values and DIPY-corrected b-vectors are at
`/app/data/sherbrooke`; `data_manifest.json` identifies their exact names,
versions, hashes and correction lineage. Use them offline. The image is
128 × 128 × 60 × 193 with one b0 and 64 volumes in each nonzero shell
(1000, 2000, 3500 s/mm²). Preserve original voxel/gradient ordering: the supplied
b-vectors already include the upstream x-direction correction. Do not flip again.
The NIfTI spatial-unit field is unknown; no physical resampling is requested.

## Declared baseline

All numerical settings, source geometry/volume indices and sphere identities
are supplied in **`/app/method_contract.json`**. This public file contains
configuration and source identity, not fitted answers. It is also a template for
your metadata. Use the installed pinned implementation, or a numerically
equivalent implementation of the same recipe.

### Fixed ROI

Read float64 data without smoothing or reorientation. Use b0 threshold 50;
round b-values with `numpy.round(bvals, -2)`. Compute a brain mask from mean b0
with `median_otsu(median_radius=3, numpass=1, autocrop=False, dilate=None)`.
Fit DTI-WLS with `min_signal=0.0001` on b0+b1000. Keep brain-mask voxels in
`data[45:83,45:90,31:36]` with finite **0.30 < FA < 0.90**. Use precisely this
same ROI for every reconstruction; do not remove voxels based on fODF results.

### Response estimation and reconstructions

Evaluate **any two or all three** named recipes: `msmt`, `csd_b1000`,
`csd_b3500`. Any submitted recipe may supply the headline; MSMT is not mandatory.

Select response masks on b0+b1000 using DIPY `mask_for_response_msmt`, centered
at `floor(shape_xyz/2)`, cube radius 10, with WM FA threshold 0.7, GM FA threshold
0.3/MD threshold 0.001, and CSF FA threshold 0.15/MD threshold 0.0032.
These are DIPY's heuristic FA/MD masks, which can overlap, not known pure tissues.

- **`msmt`:** use all shells. Estimate responses with
  `response_from_mask_msmt(..., tol=20)` from those low-b masks;
  `multi_shell_fiber_response` uses order 8, shells [0,1000,2000,3500],
  `default_sphere` and tolerance 20. Fit `MultiShellDeconvModel` with
  `iso=2`, order 8 and `default_sphere` regularization.
- **`csd_b1000` / `csd_b3500`:** use b0 and **only the named nonzero shell**.
  Estimate each response with `response_from_mask_ssst` on that subset using
  the same low-b WM response mask. Fit `ConstrainedSphericalDeconvModel` with
  order 8, `small_sphere` regularization, `lambda_=1`, `tau=0.1`,
  `convergence=50`. Do not use a mixed-shell `csd_all` comparison.

For MSMT, solve the DIPY constrained least-squares problem explicitly:
minimize `0.5*c.T@(X.T@X)@c - (X.T@signal).T@c`, subject to
`reg@c >= 0`, where X and reg are the model's response-dependent design and
nonnegativity matrices. The baseline uses CLARABEL 0.11.1's direct QP interface:
P=upper_triangle(X.T@X), q=-(X.T@signal), A=-reg, b=0, and a nonnegative
cone of dimension len(reg). Use a new solver per voxel, default settings except
tol_gap_abs=tol_gap_rel=tol_feas=1e-10, max_iter=300, max_threads=1 and
verbose=False. There is no objective rescaling or warm start. Require `Solved`
status and finite coefficients; do not silently replace failed fits by zero.

### Peak definition

Evaluate fitted WM SH coefficients in DIPY's legacy Descoteaux basis on
`default_sphere` (the repulsion724 hemisphere). CSD's regularization sphere
is different: `small_sphere`, the symmetric362 hemisphere. Their exact vertex
and edge hashes are in the public contract.

Use DIPY `peak_directions` with relative threshold 0.5, minimum separation 25°,
antipodal symmetry enabled, and retain at most the top three peaks. Do not
normalize peaks or clip the fODF before detection; this corresponds to the
`peaks_from_model` peak step with `gfa_thr=0`, `normalize_peaks=False`.
Count retained peaks with strictly positive value. A crossing voxel has at
least two. The fraction is crossing voxels divided by **all fixed-ROI voxels**.

## Deliverables

Write to `${OUTPUT_DIR}` (default `/app/output`):

- `peaks_voxelwise.csv`: columns `i,j,k,n_peaks`, one row for every fixed-ROI
  voxel under your declared primary recipe.
- `peaks_sweep.csv`: columns `i,j,k,estimator,n_peaks`, one row for every
  (voxel, submitted recipe). Coordinates and counts must be integral; counts
  are 0–3. No duplicate, missing or extra ROI coordinates.
- `crossing.json`: `status: "ok"`, `pipeline_id: "sherbrooke-fodf-v2"`,
  `primary_estimator`, `crossing_fraction`, `n_roi_voxels`,
  `n_crossing_voxels`, `mean_peaks_per_voxel`, and
  `crossing_fraction_by_estimator` (an object for exactly the submitted
  recipes). All summaries must recompute from the tables.
- `run_metadata.json`: start from `/app/method_contract.json`, retain its
  declared source/recipe fields, and add `status: "ok"`, `primary_estimator`
  and `fitted_estimators` (the recipes actually present in your sweep).
  The template describes all three **available** recipes; that does not require
  fitting the unused recipe. You may add implementation details, actual response
  arrays and fit diagnostics. Do not misdescribe your implementation.
- `findings.md`: report your primary fraction and the measured comparison.
  Explain the single-acquisition, ROI, response-selection and peak-definition
  limits. Shell/model differences do not isolate a causal mechanism or prove
  that one estimate is inflated. No required English wording.

CSV row/column order, extra descriptive columns and equivalent numeric
representations are accepted. Source geometry metadata can be rounded to six
decimal places (absolute tolerance 1e-6). Baseline per-voxel **integer counts
must agree exactly** for each declared recipe; every submitted group is checked.
JSON/CSV fractions and means must agree within 1e-6. No minimum estimator gap,
preferred direction, population plausibility range or prose keywords are graded.
Scoring is all-or-nothing, not proportional.

If source data, response selection or fitting fails, exit nonzero and write
parseable metadata/results plus findings with `status: "failed_precondition"`
and a nonempty reason. A failed-precondition run is not a successful analysis.
