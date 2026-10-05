# Validation status — 2026-10-01

Source-bound easy/method control, not unbiased diffusivity truth or the cited
rat/Rician study's finding. All three declared estimators are acceptable; a
participant submits one. No frontier-model run or empirical hardness claim.

The three original CFIN files (173,719,934 bytes, CC0) are checksum-pinned and
baked into the offline image. The 57,957-voxel brain mask yields 10,105 complete
unsmoothed low-b-FA-selected ROI voxels. Actual offline native executions give:

| Configuration | Mean MD (1e-3 mm²/s) | Mean FA | Mean normalized RMSE | Voxels with eigenvalue floor |
| --- | ---: | ---: | ---: | ---: |
| DKI all | 0.8827180934 | 0.6382943880 | 67.23681528 | 643 |
| DTI low-b | 0.8014611725 | 0.6495475103 | 66.31724899 | 656 |
| DTI all | 0.5848976228 | 0.6598604638 | 62.01974284 | 482 |

These differences do not identify an unbiased model. Eighteen retained ROI
voxels have zero observed b0 and hence the predeclared 1e-4 normalization scale;
their enormous normalized residuals dominate the means. DKI's all-voxel residual
median is 0.04336. Signal-floor counts, raw/post-floor stages and distributions
are retained, not hidden by new exclusions or retrospectively changed tolerances.

All-ROI source, tensor, prediction, residual and summary checks pass. Independent
SciPy GELSD refits of 256 predeclared rows per model match raw coefficients;
maximum diffusion-coefficient error is 5.66e-15, maximum normalized prediction
error 1.06e-7. Sixteen DIPY raw-helper comparisons per model also pass. Masking
and low-b ROI selection share DIPY; this is partial independent numerical
validation, not independent anatomical or physiological validation.

The genuine bank is rebuilt from these executions, complete source arrays and
full-ROI WLS normal-equation checks (maximum relative residual 2.06e-12).
Bank SHA256: d5b6acec4cc9656b95806303c99e0f644abbc30b98fda887a1eb8c4b2e600406.
209 native-image authoring tests pass: 66 verifier mechanics, 51 numerical,
32 staging and 60 actual-output cases (10 positive, 50 negative). Genuine
positives include every model and independently refitted 256-row alternatives.
Initial five test failures were overly specific exception matching after count
mutations became fractional; tests now mutate integer counts as integers.
Verifier decisions and measured-result tolerances were not weakened.

The sequential follow-up receipt records the final clean-commit Harbor result,
image identity, task digest and final-image tests after commit. Raw execution
logs and the failed test attempt are retained under the dated repair tracking
directory. No push, merge, PR comment or public image publication is implied.
