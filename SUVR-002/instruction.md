# Regional SUVR of a heterogeneous static-PET cohort

## Task
`/app/data/` holds a cohort of static brain-PET exams (`sub-01` … `sub-08`). Each subject has
a reconstructed 3-D PET activity image, a valid brain mask, and a region segmentation. From
these, compute the per-region **standardized uptake value ratio (SUVR)** for the target
regions and write it out.

The cohort is **heterogeneous**: every subject's sidecar declares its reference region, voxel
size, PSF, and which segmentation it provides, and you must adapt the analysis per subject — a
pipeline that assumes one fixed recipe will not fit them all. **Report a target region's SUVR
only where the data determine it; where they do not, omit that region.** There is no reference
tool provided — implement the estimator yourself and get the normalization, partial-volume
handling, units, and per-subject adaptation right.

Grading is **outcome-based against the true underlying physiology**: each SUVR you write is
compared to the *true* region-to-reference activity ratio that the acquisition determines.
**Any scientifically valid estimator is accepted** — FFT or zero-padded PSF, direct or
pseudo-inverse GTM solve, any robust regional-mean rule — because every correct method recovers
the same ratio within tolerance. You are **not** required to reproduce any particular reference
implementation's output. Partial cohorts and partial region sets are scored proportionally, so
produce every SUVR you can support and omit the rest.

## Robustness / data-quality contract  (READ THIS)
The reconstructed PET is realistic, not clean. Handle the following robustly; *which* subjects
and *which* voxels are affected is **not disclosed** — you must find them from the data:

- **Gross reference-region spill-in.** On a **majority of subjects**, a compact cluster of the
  **reference-region** voxels is grossly contaminated (hot spill-in / reconstruction artifact,
  several-fold above the region). Because SUVR divides by the reference mean, a plain mean that
  folds these in biases **every** target region. **Detect and reject** such gross voxels before
  forming the reference mean.
- **Gross target-region dead voxels.** On **several subjects**, a compact cluster of a target
  region's voxels is dead / near-zero (low-count). **Detect and reject** these before that
  region's mean. The contamination is gross (far outside the natural within-region PSF-blur
  spread), so any reasonable robust window drops exactly the same voxels.

These are the only lever beyond the pinned conventions (the per-subject reference region, the
GTM-vs-uncorrected PVC fork, the PSF sigma, and the omit rule for a target region with too few
valid in-mask voxels, all already specified above). Modest reconstruction noise is present and
does **not** need special handling beyond an ordinary regional mean.

## Graded quantity (`/app/data/protocol.json`)
A single JSON fixes the physics and conventions common to all subjects and **defines the
graded quantity**:

- **SUVR** of a target region is dimensionless: `corrected_mean(target) /
  corrected_mean(reference_region)`, where `reference_region` is the region **named in each
  subject's sidecar**. Because SUVR is a ratio, the global SUV scale (injected dose, body
  weight, calibration) cancels and need not be applied.
- **Partial-volume correction.** Where a subject ships a **full-volume parcellation**
  (`parc.npy`, every voxel labelled — a partition of the whole image), report **GTM (Rousset)
  region-based partial-volume-corrected** regional means: one geometric-transfer matrix built
  from the parcellation and the Gaussian PSF, solved for the regional true activities, and form
  SUVR from those. Where a subject ships only **sparse ROI labels** (`roi.npy`, target and
  reference regions labelled and everything else `0`), GTM is not supported — report the
  **uncorrected** regional-mean ratio instead.
- **PSF.** An isotropic 3-D Gaussian of the sidecar's `psf_fwhm_mm`; its standard deviation in
  voxels is `fwhm_mm / voxel_size_mm / (2·sqrt(2·ln2))`.

Read the protocol before you start: it lists the region legend, the target regions, the
reference regions, and the exact output contract.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `shape`, `voxel_size_mm`, `psf_fwhm_mm`, `reference_region`, the PET/mask
  file names, and **either** `parcellation_file` (→ `parc.npy`) **or** `roi_file` (→
  `roi.npy`).
- `pet.npy` — the static PET activity image, float32, shape `shape` (in the subject's voxel
  order).
- `mask.npy` — the valid brain mask (same shape; SUVR is formed over valid voxels).
- `parc.npy` **or** `roi.npy` — the region segmentation (integer labels; see the protocol
  legend).

## Required output (`/app/output/sub-XX/`)
Write `suvr.json`: a JSON object mapping each **supported** target-region name to its SUVR (a
float). **Omit** (leave the key out) any target region the data cannot support. Report SUVR for
target regions only — not for the reference region.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid SUVRs for the
regions you can produce so the rest of the cohort can be graded.
