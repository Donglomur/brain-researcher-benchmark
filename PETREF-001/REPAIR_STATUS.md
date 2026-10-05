# Validation status — local follow-up, 2026-10-01

## Scope and source corrections

Retained as a public-recipe **midpoint SRTM method/easy control** on two people's
four original PETPrep TACs. It is not a published putamen BP reproduction or a
population-reliability result. Uncomputed whole-reference/PVC effects and
cross-estimator agreement claims are removed, along with hidden BP/R1/retest
bands, variability floors, partial scan matches and prose gates.

OpenNeuro ds001420 snapshot 1.2.0 contains 24 selected original source/lineage
files totaling 270,682 bytes. Direct text files match published Git blob hashes;
annexed logs/reference TACs match published pointer hashes, sizes and MD5.
Additional SHA256 pins are in the final source manifest.
Commit: `2b21a6d6e57cf712ec068faf594be4bbf14cdcbe`.
Actual root tree: `c937d6f6c05c0e7c788190f4962c0393534a7212`.
The original tag-resolved API response echoed the commit as its top-level SHA;
the commit API and actual-tree lookup establish the distinction. Earlier
inspection evidence is retained, not silently overwritten.

The pinned root metadata says **CC0**, contrary to the old proposal. Supplemental
participants metadata confirms exactly sub-01/sub-02. All 140 TAC frame bounds
match raw PET metadata: 32 frames/53.6 minutes for sub-01 baseline, 36 frames/
90 minutes for the other three. Times, injection/scan origin and decay-correction
time are checked. Units are inherited from Bq/mL PET metadata and no-rescale
extraction logs; absent TAC sidecars and missing derivative dataset metadata are
disclosed. Image preprocessing/extraction was not rerun.

The generic `reference` column matches the original AGTM `km.ref.tac.dat` within
9.1e-13 in every scan; logs name cerebellar cortex labels 8 and 47. The old claim
that it combines white matter and vermis as 'whole cerebellum' is unsupported.
The repaired analysis uses the explicit no-PVC left/right cortex columns instead.

## Executed genuine-source computation

All original source files were reacquired and checked during Docker build.
The native oracle runs with network disabled, 2 CPUs and 8 GB; no source cache
or upstream fitted parameter table is used.

The declared model uses equal-hemisphere means, minutes, linear reference
interpolation through (0,0), stable analytic convolution, and three prespecified
TRF starts. It compares midpoint observations, not exact frame-average predictions.
All 12 optimization attempts converged. Four selected BP_ND estimates are:

- sub-01 baseline: 1.9601285452; rescan: 1.9816933597.
- sub-02 baseline: 1.9004647688; rescan: 1.9388412142.

Mean BP_ND is 1.9452819720. Per-person repeat differences are 1.094154686% and
1.999134511%; mean 1.546644598%. No selected parameter is at its declared bound.
Normalized residual RMSE is 0.01864–0.02794. These are conditional method outputs;
unequal durations, preprocessing and model assumptions limit interpretation.

An independent checker rereads original TACs and sidecars and validates every
frame, input mean, parameter identity, residual/QC and paired summary. Adaptive
ODE integration agrees with the analytic predictor within 1.98e-14 normalized
units. A separate augmented-matrix-exponential predictor and complex-step
Jacobian, fitted with dogbox, agree within 2.28e-8 across parameters and
6.21e-9 in normalized prediction. SciPy is shared; this is numerical agreement,
not biological ground truth. Normalized Jacobian condition numbers are
19.29–49.94; multistart parameter spread is <=2.90e-8, not a general uncertainty
or identifiability certificate.

Source-validated reference regenerated from these actual outputs; the stale
coarse-grid bank is not relabeled. Every required scan/frame is verified.
Optimizer-history fields are checked semantically, not treated as execution
attestations; private candidate arrays are not required participant outputs.

## Acceptance evidence boundary

Native original-source validation and independent numerical checks are complete.
The final authoring suite includes staging/model/schema fixtures, genuine output
positives, a genuinely refitted alternate optimizer, and coherent
source/parameter/prediction/QC/pairing forgeries. Final counts and clean-commit
Harbor acceptance are recorded after commit in the external receipt:

`/home/zijiaochen/projects/brain_researcher_benchmark/tracking/pr_repairs_2026-10-01/pr-150/receipt.json`.

That receipt identifies commit, task digest, image, raw result/config/lock,
oracle/verifier logs and output comparison. Native tests alone do not establish
the final Harbor reward. Original/native/independent evidence is retained under
`/home/zijiaochen/projects/brain-researcher-benchmark-runs/20261001/pr150-*`.

No Sol/frontier trial, push, PR comment or merge is included. Model difficulty,
maintainer acceptance and biological interpretation remain separate decisions.
