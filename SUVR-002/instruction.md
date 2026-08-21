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

Grading is **outcome-based**: each SUVR you write is recomputed from the PET by a held-out
reference and compared value-by-value. Partial cohorts and partial region sets are scored
proportionally, so produce every SUVR you can support and omit the rest.

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
