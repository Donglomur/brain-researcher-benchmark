# PVFA-001: diffusion-model sensitivity in a source-defined proxy ROI

Compare conventional tensor FA and two-compartment tissue-tensor FA on one
original Sherbrooke diffusion acquisition. This is a paper-derived **method
case**, not an original-cohort finding, validated ventricular localization,
or a test against known tissue FA. The historical task ID is retained for PR
continuity; the scientific target and output names no longer imply anatomy.

## Paper and data connection

The two-compartment signal model follows Henriques et al. (2017), Eq. 1 and
its WLS/NLS methods, implementing the approach of Hoy et al. (2014). These
methods motivate comparing model-dependent estimates; they do not establish
which estimate in this acquisition is the biological truth.

- [Hoy et al. 2014](https://doi.org/10.1016/j.neuroimage.2014.09.053)
- [Henriques et al. 2017](https://doi.org/10.5281/zenodo.495237)
- [Original Sherbrooke deposition](https://digital.lib.washington.edu/researchworks/handle/1773/38475)

The three inputs are 192,519,151 bytes: original image and b-values plus the
documented upstream DIPY orientation-corrected b-vectors. Published MD5 anchors
and verified SHA256 pins are retained. The CC0 source is baked offline. No
synthetic cohort or another task's masks/fits/answers are substituted.

## What changed

The NIfTI header has zoom values of 2 but does not declare spatial units. The
recipe therefore states FWHM **0.625 voxels**, without asserting a physical-mm
length. The ROI is explicitly a low-b-DTI-defined high-MD/low-FA-adjacent tissue
proxy. It is not called a ventricular segmentation or independent white-matter
label. Its data-dependent selection is shared across the compared models.

All three numerical recipes are public. Any two are acceptable, including the
two single-tensor fits; no hidden free-water requirement, effect direction or
minimum contrast remains. The free-water implementation preserves the actual
fitted S0, raw tensor, convergence status and signal residuals. Initialization
sentinels and skipped/failed fits are not mistaken for converged tissue fits.
Every ROI coordinate remains represented, with explicit validity and denominators.

Complete model-bound parameter tables replace correlation/overlap matching and
loose mean bands. Predictions, residuals, eigenvalue clipping, FA and summaries
are recomputed. The reference must be regenerated from original inputs under
this public recipe; the previous 1,740-voxel bank and numerical conclusions are
superseded, not relabeled as current evidence.

## Interpretation and readiness

Fitted isotropic signal fraction is not independently measured CSF volume.
Clipped tensor FA is a disclosed computational summary; a larger value does not
prove recovery of true tissue microstructure. Convergence does not establish
parameter identifiability, and no residual or Jacobian cutoff is chosen after
seeing the data. Native fits, independent checks, final-image tests and Harbor
acceptance are recorded separately in REPAIR_STATUS.md and dated receipts.
This is an easy/method control with no new Sol difficulty claim. No push, merge,
PR comment or model calibration is part of the local repair.
