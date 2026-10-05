# PERFDIFF-001 repair evidence

## Scope and implemented repairs

Retain as an easy, paper-derived method control, not a finding reproduction or
validated physiological perfusion estimate. The public Peterson Figshare v1
image is registered and direction-averaged, not raw diffusion directions. The
three source files (274,689,129 bytes) are pinned against published MD5 checksums
and verified SHA256 digests, then baked offline. The deposited fitted image is
excluded. Source/licensing/provenance limitations are explicit in the manifest.

Replaced warning-suppressed default-DIPY fallback behavior with public explicit
full TRR and segmented-b200 recipes. The segmented second step fits original
low-b signal rather than a clipped/logged residual with a discarded intercept.
Retain all 900 box coordinates under both methods, full S0/f/D/Dstar estimates,
optimizer diagnostics, failed candidates and parameter-boundary flags. Only
initializers are projected; failed optimizers do not silently become successes.
Shared-set comparisons use the actual intersection of numerical admissibility.

The source-bound bank is regenerated from actual fits and retained signals,
parameters, predictions and statuses. The verifier joins every output table by
identity, reconstructs signal/NRMSE, and recomputes own/common-valid summaries
and signed differences. Partial coverage, correlation-only acceptance, invented
diffusivities, hidden fitting settings, expected spread and prose gates are removed.

## Native execution evidence

All 900 voxels are source-eligible. Own-admissible counts are 899 for full TRR
and 839 for segmented-b200; 838 are common. On that identical set, mean f is
0.4768977043 versus 0.1214692678, with signed segmented-minus-TRR difference
-0.3554284365. No minimum difference or direction is graded.

Independent source/coordinate/centered-OLS/equation/objective/derivative/QC checks
pass. Predicted signals and residuals recompute exactly; maximum independent
initializer difference is 3.00e-15. A 32-row alternate dogbox solve converged on
all sampled rows, yet normalized parameter differences reach 0.0191 while maximum
prediction difference is only 4.04e-6 times b0 and mean-squared-error difference
5.02e-12. A sampled scaled Jacobian has condition number 3.07e9. These diagnostics
show why tight recipe repeatability must not be advertised as unique parameter
identification; the alternative solve is diagnostic only, sharing SciPy/objective.
Actual-output and authoring regressions: **159 passed** (62 mechanics, 23 source
staging, 12 numerical fixtures, 61 output variations/mutations and 1 template check).

## Scientific limits revealed by execution

The large fraction difference is not evidence of perfusion identification.
Full TRR has 367 near-zero-D flags (343 in the common set), 48 projected
initializations and 48 canonical component swaps. The segmented method has
61 inadmissible high-b initializations and 92 near-coincident-D/Dstar flags
(91 in the common set). Boundary flags are diagnostics, not post-hoc exclusions.
Strict numerical admissibility and low residuals can still leave components
weakly separated. Preserve precision when serializing near-boundary values.
The common-set comparison is conditional on both recipes, not a population effect.

## Final-container gate

Clean-commit Harbor reward, final image/content identity, repeated parameter
agreement and final-image regression results must be read from the external
`tracking/pr_repairs_2026-10-01/pr-145/receipt.json`, not inferred from these
native checks. No Sol/frontier calibration, push, PR comment or merge is implied.
