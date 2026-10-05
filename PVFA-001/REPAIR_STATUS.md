# Source-bound method-control repair

This is a single-acquisition, paper-derived computational model-sensitivity
case, not validated ventricular anatomy, recovered tissue ground truth, an
original-cohort finding, or evidence of coding-agent difficulty.

Original Sherbrooke image/b-values and upstream-corrected b-vectors are pinned
by size/SHA256 and baked into the offline image. Spatial units are unknown in
the original NIfTI header; the public kernel is explicitly 0.625 voxels FWHM,
not a claimed physical-mm length. The threshold-derived ROI is named a proxy.

The full public recipe retains fitted S0, raw tensors, optimizer termination,
skipped/failed fits, predictions, residuals and eigenvalue clipping. Any two
or three models are accepted, including DTI-only. Complete ROI identity and
source-bound parameter receipts replace hidden preferred-model/spread gates.
Summary statistics are recomputed on both own-model and selected-common support.

## Measured local evidence before final container validation

- Original source: 3 files, 192,519,151 bytes, CC0. Manifest SHA256
  `f59a83a45da820308010d02ea93a29291df1bee117a66f399ddc95978c6be2fa`.
- Full source-defined ROI: 4,083 voxels; all three models were genuinely run.
  No captured fit warnings, but convergence is not scientific validity.
- FW eligible support: 3,727. Mean FA is 0.63654154; DTI b0+1000+2000
  is 0.56492834 and DTI b0+1000 is 0.38124532 on each model's own support.
- FW clips 2,890 eigenvalues in 1,551 voxels; 356 converged candidates have
  zero reported tissue tensors and are ineligible. DTI b0+1000+2000 clips
  1,630 eigenvalues in 1,089 voxels. These are substantial model limitations,
  not observations of biological recovery. No post-hoc rows were removed.
- Independent original-source/ROI/all-row arithmetic checks passed; 64
  separately solved WLS and analytic-Jacobian LM fits per model agree within
  public tolerances. TRF is diagnostic, not automatically a passing recipe.
  Reader, mask/filter routines, numerical libraries and acquisition are shared;
  this is not independent tissue truth or a full nonlinear refit of every row.
- A separate actual DTI-only execution passes the verifier.
- The bank was regenerated from genuine source receipts, not relabeled from
  the old bank. Pipeline: `sherbrooke-proxy-fa-v2`. Bank SHA256:
  `dae9ac968a4f560f08b268abdfc54677b0679e74b040d4e4ec8c01f7ab0f0aff`.

Final clean-commit Harbor output, image identity, content digest and regression
results belong in the external dated repair receipt; they are not claimed by
this pre-run document. No Sol/frontier run, push, merge or PR comment was made.
