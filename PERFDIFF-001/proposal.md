# PERFDIFF-001: IVIM fitting and numerical-admissibility sensitivity

## Scientific scope

Retain as a paper-derived **method / easy control**, using the modern
biexponential signal model implemented by DIPY. [Le Bihan et al. (1988)](https://doi.org/10.1148/radiology.168.2.3393671)
provides the foundational diffusion/perfusion separation context; this task
does not reproduce its historical acquisition, cohort, figure or clinical finding.

[Barbieri et al. (2016)](https://doi.org/10.1002/mrm.25765) motivates fitting-method
sensitivity using upper-abdominal data, and [While (2017)](https://doi.org/10.1002/mrm.26598)
studies fitting approaches through simulations. Neither is the source cohort
for this single public brain acquisition. No numerical spread, estimator ranking,
population range, or physiological ground truth is assumed.

## Public substrate

Use [Eric Peterson's IVIM dataset, Figshare v1](https://doi.org/10.6084/m9.figshare.3395704.v1).
The deposited image is already registered and averaged across three directions,
yielding 21 b-value volumes. It is not raw direction-resolved diffusion data.
Only the source image, b-values and b-vectors are used; the deposited fitted
parameter image is deliberately excluded.

The versioned source identities, published MD5, verified SHA256, byte sizes and
CC0 licensing are recorded in the manifest. Original bytes are downloaded at
image-build time and supplied offline. The task does not synthesize a cohort or
silently substitute cached data.

## Numerical and scientific repair

The old default-DIPY output mixed optimized parameters with initialization/fallback
returns, while globally suppressing warnings. Its two methods also used different
valid-voxel denominators. Consequently, an apparent difference could combine
algorithm behavior, failed fitting and sample selection. Old reference numbers
and claims that they demonstrate a particular scientific effect are withdrawn.

The revised public baseline explicitly specifies:

- Full bounded nonlinear fitting with observed-b0 signal normalization, analytic
  derivatives, initialization, optimizer settings and recorded termination.
- A named segmented b200 approximation, with high-b log-linear tissue estimation
  followed by an original-signal low-b fast-component fit. It does not clip and
  re-log residuals or discard a fitted low-b intercept.
- Every coordinate in the fixed box remains represented, including source-ineligible,
  failed and degenerate rows. Initialization projection is recorded, never silently
  substituted for a failed nonlinear solution.
- Separate per-method admissibility counts and a shared, paired comparison set.
  Bounds and ordered components are numerical definitions, not validated biological
  ranges or a test of parameter identifiability.
- Retained measured/predicted signals and residuals, with no post-hoc residual or
  minimum-spread exclusion.

The exact contract is public in the instruction and metadata template. This is
a comparison of two specified computational recipes, not a claim that only these
estimators are scientifically valid.

## Verifier and validation

Bind full S0/f/D/Dstar estimates and statuses to source-derived coordinates and
the declared recipe, not just a correlated f map. Join primary, sweep and parameter
tables by identity; reconstruct predicted curves and residuals, recompute validity
and common-set summaries, and preserve signed paired differences.

Reject missing/padded/duplicate coordinates, fabricated diffusivities, copied
second methods, forged success masks, wrong denominators, disconnected tables
and incorrect source/recipe metadata. Accept equivalent numeric formatting,
row order, additional descriptive columns and either permitted primary method.
No English keywords, mandatory difference or direction are graded; scoring is
all-or-nothing.

A genuine source-run bank, independent signal/derivative checks, repeatability,
actual-output regression matrix and clean-commit in-container oracle are separate
validation gates. Small authoring fixtures alone establish none of these.
Actual execution status belongs in REPAIR_STATUS.md and the retained external
receipt, not a historical proposal claim.

## Limits and delivery

A low residual or successful optimizer does not establish a unique or unbiased
perfusion parameter. The source image is already processed, the ROI is operational,
and this is one acquisition. No Sol/frontier run, scientific acceptance, push or
merge is implied. Public answer material also requires contamination-aware later
model evaluation.

Resource ceiling: 2 CPU, 8 GiB RAM, no GPU, 3600 s agent, 900 s verifier.
