# Offline, source-derived DKI method-control repair

Three original CFIN image/gradient files were downloaded from immutable UW
ResearchWorks bitstreams and matched to published MD5 plus recorded SHA256
checksums. They are baked into a network-disabled image. No shared data cache or
runtime fetch is required.

Instruction, oracle and verifier now share a public physical-mm smoothing,
DTI-WLS fixed ROI, DKI-WLS and actual shell-cap contract. The new
`cfin-physical-wls-v2` reference was rebuilt from real original source data,
retained model parameters and signal residuals. No bank-derived fake oracle was
used. Complete ROI/cap membership, per-voxel magnitudes, all submitted groups,
strict arithmetic and source/estimator metadata are checked. Correlation-only
gates, required monotonicity/spread and English keyword gates are removed.

Measured native offline baseline: 17,170 ROI voxels; MK means 0.8903321176,
0.8791209720, 0.8870570908, 0.8794627170 and 0.8553441721 at caps 1000, 1400,
2000, 2400 and 3000 respectively. The actual spread is 0.0349879455 and is not
monotonic, invalidating the old predetermined 0.05/decline gate.

A separate NumPy two-step WLS solve on 256 deterministic voxels per cap agrees
with the pinned fitter (maximum MK difference 7.47e-11). Source preprocessing,
DTI selection, model design, parameter conversion, MK and prediction share
libraries; this is bounded numerical verification, not biological ground truth.
Severe fit outliers remain: cap-2000 NRMSE exceeds 0.1 in 1,210 voxels and 1 in
173; 1,213 MK values hit zero. Large kurtosis components at near-zero MD can
agree numerically yet be scientifically implausible. Findings expose these QC
limits without silently deleting outcome-selected voxels.

Native actual-output authoring tests: 74 passed (23 parser/geometry/physical,
15 source staging, 8 accepted equivalents and 28 rejected mutations).

Role: paper-derived method/easy control, not a reproduction of Jensen's original
cohort, an unbiased physiological MK estimate, or a hard-model-failure claim.
The exact clean-commit Harbor state, actual final-image regressions and artifacts
are recorded externally in tracking/pr_repairs_2026-10-01/pr-143/. This text alone
is not an oracle result. No push, merge or model calibration is implied.
