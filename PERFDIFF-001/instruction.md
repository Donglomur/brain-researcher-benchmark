# IVIM fitting and numerical-admissibility sensitivity (PERFDIFF-001)

## Scientific target and data

Compare two specified fitting recipes for the modern biexponential IVIM signal:
`S(b) = S0 * [f*exp(-b*Dstar) + (1-f)*exp(-b*D)]`.
Report fitted fractions/diffusivities, fitting failures and the paired method
comparison. D and Dstar are in mm²/s; f is dimensionless.

[Le Bihan et al. (1988)](https://doi.org/10.1148/radiology.168.2.3393671)
provides the foundational IVIM context. This is a **paper-derived method control**,
not a reproduction of its cohort, historical protocol or clinical findings.
A good signal fit does not establish identifiable or unbiased perfusion parameters.

The original files of [Peterson's public IVIM dataset v1](https://doi.org/10.6084/m9.figshare.3395704.v1)
are baked into `/app/data/ivim`. Its manifest provides exact source identities,
checksums and geometry. The image was already registered and averaged across
three directions before deposition: 21 b-value volumes from 0 to 1000 s/mm²,
not raw direction-resolved measurements. The deposited parameter-fit image
is not supplied or used as truth. Work offline.

## Public baseline

Use the settings and metadata template in **`/app/method_contract.json`**.
It contains source/configuration, not fitted answers. Either recipe can be
primary, but submit both `trr_explicit` and `segmented_b200`. Use the pinned
implementation or a numerically equivalent implementation of these recipes.
No particular difference, direction or estimator ranking is required.

### Source coordinates and signal

Preserve the original array orientation, with no resampling or smoothing.
Retain **all 900 coordinates** in x=[90,120), y=[90,120), z=33.
For each voxel, S0obs is the mean of measurements with b=0 (`b0_threshold=0`).
Source tissue eligibility is S0obs greater than half the median positive S0obs
within the box. Keep ineligible and failed rows in every output; do not silently
change the ROI or drop high-residual fits.

For eligible, finite, strictly positive measurements, fit normalized signal
`y = S/S0obs`. Nonpositive/nonfinite source measurements cannot enter the
log-linear initialization: flag them, without clipping them into apparent success.

### Full fit: trr_explicit

Fit q=[a,f,Dstar,D], where a=S0fit/S0obs, to all normalized measurements.
Use SciPy `least_squares`, TRF, linear loss, exact trust-region solver,
analytic Jacobian, x_scale=[1,0.1,0.01,0.001],
ftol=xtol=gtol=1e-10 and max_nfev=1000.

Bounds are a≥0, 0≤f≤1, and 0≤D,Dstar≤1. These are computational guards,
not physiological reference ranges. Initialize by ordinary least-squares
log-linear fits: b≥400 yields Ahi and D0; b≤200 yields a0 and Dstar0;
f0=1-Ahi/a0. Project only the initializer to a≥1e-8,
f∈[1e-6,1-1e-6] and D,Dstar∈[1e-8,1-1e-8], recording whether it changed.
Never return an initializer as a successful nonlinear fit.

If a converged solution has Dstar<D, swap the two coefficients and replace
f by 1-f, recording the swap. This preserves the predicted curve and assigns
the fast component consistently; it does not prove a perfusion mechanism.
S0fit=a*S0obs.

### Segmented fit: segmented_b200

Set S0fit=S0obs. Fit log(y)=log(A)-b*D by ordinary least squares on b≥200;
set f=1-A. Require 0<f<1 and 0≤D<1 before the low-b fit; otherwise retain
the row and flag it as `segmented_out_of_bounds`.
For admissible f and D, fit only Dstar on the **original normalized low-b
signal** (b<200), keeping f and D fixed. Do not log a clipped residual or
fit and discard a free low-b intercept.

Use the same nonlinear solver/tolerances, x_scale=0.01 and Dstar bounds [D,1].
Initialize at 0.01 projected to
[D+1e-8*(1-D), 1-1e-8*(1-D)]. Record termination and boundary diagnostics.

### Numerical QC and comparison

A numerically admissible row must be source-eligible, successful and finite,
with S0fit>0, 0<f<1 and 0≤D<Dstar≤1. Record failure/degeneracy separately.
Boundary hits and projected initialization must be disclosed; they are not
additional hidden exclusion criteria. No fallback solution is permitted.

Compute each method's own admissible count and means. Separately compute the
**common-valid intersection** and compare the two methods on exactly those
same coordinates. Report signed `segmented_b200 - trr_explicit` differences.
Do not compare means over different selected voxel sets as a paired effect.
If the common set is empty, report that failure rather than fabricate means.

For every defined candidate, reconstruct its biexponential curve and
NRMSE=`sqrt(mean((prediction-S)^2))/S0obs` over all 21 measurements.
Report numerical fit QC, but do not use a post-hoc residual threshold to select
the comparison set. Numerical admissibility is not physiological identifiability.

## Outputs

Write to `${OUTPUT_DIR}` (default `/app/output`):

- `parameters_voxelwise.csv`: one row per (coordinate, method), with
  `i,j,k,method,S0,f,Dstar,D,status,optimizer_status,nfev,init_projected,component_swap,bound_flags,fallback,eligible,common_valid,nrmse`.
  Retain all rows, including failures. Undefined quantities use empty cells,
  not a fabricated number. Use the status/flag definitions in the public contract.
- `f_voxelwise.csv`: `i,j,k,f` for all 900 coordinates under the declared
  primary method, joined exactly to its parameter rows.
- `f_sweep.csv`: `i,j,k,method,f` for all 900 coordinates under each method,
  joined exactly to its parameter rows.
- `ivim_results.json`: `status: "ok"`,
  `pipeline_id: "ivim-explicit-qc-v2"`, `dataset_id: "ivim-figshare-3395704-v1"`,
  `primary_method`, `diffusivity_units: "mm^2/s"`, `n_box_voxels`,
  `n_tissue_voxels`, `n_eligible_voxels`, and `fits` containing
  each method's `method,n_voxels,S0_mean,f_mean,D_mean,Dstar_mean,nrmse_mean`.
  Include `common_valid` with `n_voxels`, `by_method` (the same summaries
  on the common set) and `paired_differences.segmented_minus_trr` containing
  the five signed mean differences. Do not use NaN/Infinity in JSON.
- `run_metadata.json`: start from the public metadata template, retain its
  source/recipe fields, and add `status`, `primary_method`, `fitted_methods`,
  `n_box_voxels`, `n_tissue_voxels`, `n_eligible_voxels`, `n_common_valid_voxels`
  and `status_counts` (each declared status for each method). You may add diagnostics.
- `findings.md`: describe the measured comparison and QC limitations, including
  source processing, voxel-selection effects and parameter-identifiability limits.
  No prescribed English wording, scientific effect or minimum gap is required.

Equivalent numeric notation, reordered rows/columns and additional descriptive
columns are accepted. Coordinates and flags must have their declared discrete
values; retain enough parameter precision that rounding does not change a row's
admissibility or boundary flags. All source identities and recipe labels are checked. The public contract
specifies parameter-specific numerical tolerances and arithmetic tolerances.
This finite computational baseline does not reject other estimators as science;
they would require a separately validated extension. Scoring is all-or-nothing,
not proportional.

If source loading or analysis preconditions fail, exit nonzero and still write
parseable metadata/results and findings with `status: "failed_precondition"`
and a nonempty reason. Failure is not a successful scientific result.
