# FODCROSS-001 repair evidence

## Scope

Retain as an easy, paper-derived **method control** on the public Sherbrooke
acquisition, not as the original Jeurissen cohort finding or biological fibre
ground truth. No Sol/frontier model run or difficulty claim is made.

## Implemented

- Three original source files are size/MD5/SHA256-pinned and baked into the
  network-disabled image. The b-vectors use DIPY's documented upstream correction;
  image/b-values retain their original UW bytes. The source manifest retains the
  correction lineage and the image's unknown NIfTI spatial-unit declaration.
- Public source/geometry/ROI/response/solver/peak contract is available in
  `/app/method_contract.json`. Any two of MSMT, b1000-only CSD and b3500-only CSD
  are accepted; any submitted method can supply the primary fraction.
- Removed mixed-shell single-shell CSD (`csd_all`). Response masks use low-b DTI;
  the same low-b WM mask supplies both single-shell response estimates.
- Verifier requires exact complete ROI membership, unique integral coordinates
  and peak counts, method-specific maps, primary/sweep identity and recomputed
  arithmetic. There is no mandatory MSMT, expected gap/direction, population
  plausibility or English keyword gate.
- Retain full fitted SH coefficients, fODFs, peak indices/values, responses,
  raw-signal residuals and solver diagnostics. No peak-outcome ROI filtering.

## Numerical repair

The first real-source MSMT run failed at ROI row 1047 (`[51,58,34]`): raw-scale
OSQP exhausted 100,000 iterations and reported `optimal_inaccurate`. That failed
attempt is retained outside the task and is not counted as a successful oracle.
An equivalent objective-normalization probe resolved that voxel, but full-source
independent checking exposed remaining fODF discrepancies despite successful
solver statuses. Tighter OSQP settings again failed on some source voxels. All
failed/provisional attempts remain in the external execution record.

The final public baseline instead solves the unchanged unscaled QP directly with
CLARABEL 0.11.1, tolerances 1e-10 and a fresh solver per voxel. All 5,060 fits
converged (at most 21 iterations). Independent thin-QR/dual-NNLS solves on 64
deterministic rows plus the original failure sentinel agree under the original,
unchanged validation tolerances: maximum signal difference 1.91e-6 times b0;
maximum fODF difference 4.68e-5 times peak amplitude. The independent method
avoids squaring the design's condition number and retains KKT diagnostics.
The less accurate provisional peak maps are not used as reference targets.

## Execution gates

The source-bound bank was rebuilt from genuine retained fits and the exact source
ROI/responses. Independent SH, graph-based peak detection and signal residual
recomputation agree for all 5,060 voxels under all three recipes. Genuine-output
regressions pass: **107 tests** (37 parser/arithmetic, 19 source-staging, 4 solver,
11 positive output variations, 35 negative mutations and 1 public-template check).

Measured crossing fractions: MSMT 0.3274703557, b1000 CSD 0.4567193676,
b3500 CSD 0.4519762846. These are recipe-specific measurements, not true fibre
prevalence. Median DWI RMSE/b0 is 0.129991 / 0.132655 / 0.110068 respectively;
4,651 / 4,666 / 3,560 voxels exceed the disclosed diagnostic level 0.1. CSD's soft
regularization does not ensure nonnegative fODFs everywhere. No voxel was removed
because of these outputs, and there is no validated physiological QC claim.

Clean-commit Harbor reward, image/content identity, repeated map agreement and
final-image regression results must be verified in the external receipt, rather
than inferred from the native run or this source file. Receipt path:
`tracking/pr_repairs_2026-10-01/pr-144/receipt.json` in the local tracking workspace.

Source/response geometry and some DIPY components are shared by independent checks;
numerical agreement does not prove anatomical validity, pure response tissues,
unique fibre populations or population-level prevalence.
