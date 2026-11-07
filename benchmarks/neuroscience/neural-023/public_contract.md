# NEURAL-023: score submitted across-day velocity predictions

This component scores a completed prediction file for the existing Indy 2016-10-05 → 2016-10-06 development task. It does not execute the submitted method or verify training/selection provenance. The predictor's access rules and any future arbitrary-program or investigator evaluation remain separate contracts.

Submit one ordinary NPZ containing exactly two arrays:

- `case_id`: shape `(22091,)`, signed or unsigned 16-, 32- or 64-bit integers. Include every integer ID from **3010 through 25100 exactly once**. Row order may differ; scoring joins and sorts by these public IDs.
- `velocity_m_s`: shape `(22091, 2)`, finite IEEE float16, float32 or float64 values in **m/s**, ordered x then y. These predict the fixed trailing 20 ms velocity at each endpoint, not future movement.

Standard stored and deflated NPZ archives, either byte order and C/Fortran array storage are accepted. NPY header versions 1–3 are supported. Archives are limited to 1,000,000 bytes on disk and 600,000 uncompressed bytes, with headers at most 4,096 bytes. Object/structured arrays, extra or duplicate members, encrypted or linked entries, missing/duplicate/wrong IDs, wrong shapes and nonfinite predictions are invalid. These limits exceed the complete float64/int64 payload; no amplitude clipping or hidden positive-score threshold is applied.

The primary score is the arithmetic mean of x-axis and y-axis R² on all 22,091 assessment rows. Negative R² is valid. If either target axis is constant, its R² and the primary score are undefined rather than silently dropping that axis. Secondary outputs include per-axis R², MSE and MAE, whole-panel MSE/MAE, and descriptive fixed 3,000-row clock blocks including the shorter final block. MSE has units `(m/s)²`; MAE has units `m/s`. Blocks are not independent biological units.

Signed comparisons retain all seven fixed references from the completed reference stage: zero velocity, source mean, calibration mean, source-only ridge, source ridge plus calibration residual offset, calibration-only ridge and equal-day pooled ridge. Higher R² differences and positive reference-minus-candidate error differences indicate improvement under the respective metric. References are reused from their immutable scored report; no fit is repeated. There is no composite scientific-success flag and no requirement to outperform a reference.

The grader validates the complete public submission before opening private targets, then independently checks candidate metric arithmetic. Schema rejection reports zero private target loads. A valid finite submission whose metric arithmetic exceeds supported numeric range receives `unsupported_numerical_result` and a null score, not an invented finite value or an amplitude-based rejection. A discrepancy in the independent audit is an operator failure.

This is one animal, one transfer pair and exposed development assessment. Causal feature extraction in the fixed reference does not establish causal online access for arbitrary agents receiving overlapping windows in a batch. No unseen-test, population, SOTA or LLM-performance claim follows from a score.

The isolated file-scoring component passed the qualification recorded in the package manifest. Ordinary common-CLI integration is a separate check. This qualification does not establish a full research benchmark, submitted-program provenance or new scientific performance.
