# T1w/T2w myelin-proxy mapping across a heterogeneous cohort

## Task
`/app/data/` holds a cohort of coregistered T1-weighted + T2-weighted exams
(`sub-01` … `sub-08`). From each subject's two weighted images, estimate the per-voxel
**T1w/T2w myelin proxy** and write it out.

The two weighted images share the receive-coil sensitivity, so their **ratio** removes it, but
each acquisition carries an independent, arbitrary intensity scale: the raw ratio is only
determined up to an unknown per-subject constant. Your deliverable is the **convention-invariant**
readout — the ratio referenced/calibrated so that the arbitrary per-subject scale is removed and
values are comparable across subjects. Get the physics, the normalisation, and the per-subject
adaptation right.

The cohort is **heterogeneous**: every subject's sidecar declares the arrays it provides, and you
must adapt per subject — a pipeline that assumes one fixed recipe will not fit them all. **Compute
a map only where the subject's data determines it; where it does not, omit that map.**

Grading is **outcome-based and voxelwise against the true underlying anatomy**: each map you write
is compared voxel-by-voxel, inside the brain mask, to the *true* convention-invariant myelin proxy
(the referenced/calibrated `M_true = T1w_true/T2w_true`). **Any scientifically valid estimator is
accepted** — the bias-corrected ratio is a deterministic function of the images and the only region
statistic is a robust mean on which every reasonable gross-outlier rule agrees, so every correct
method recovers the same map within tolerance. You are **not** required to reproduce any particular
reference implementation's output. Each (subject × map) is scored independently and partial
cohorts/map-sets are scored proportionally, so produce every map you can support and omit the rest.
The readout follows the T1w/T2w myelin-mapping construction of Glasser & Van Essen (2011).

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the **ratio model**
(`raw_ratio = T1w/T2w = k · M_true · rho`, with `k` the arbitrary per-subject scanner scale and
`rho` the residual bias), the **bias convention** (the bias-corrected ratio is
`R_corr = (T1w/T2w) / rho`), the exact definitions of **myelin_norm** and **myelin_cal**, the
fixed calibration **targets**, the **unit** of each quantity, and the **tissue legend**. Read it
before you start.

## Robustness / data-quality contract  (READ THIS)
The images are realistic, not clean:

- **Gross T2w drop-out voxels.** In a **minority of subjects, a small fraction of voxels are gross
  T2w drop-outs** (susceptibility / edge / CSF partial-volume), where the T2w signal collapses and
  the corrected ratio spikes to roughly **100×** the physiological value. These drop-outs sit
  **inside the white-matter reference region and the high-myelin landmark ROI**, so a plain
  (non-robust) region mean is dragged upward and the resulting normalisation / calibration rescales
  the **whole** map incorrectly. **You must exclude such gross-outlier voxels from the region means
  robustly before referencing/calibrating** (any reasonable gross-outlier rule works — they are
  ~100× the physiological spread and uniquely separable). *Which* subjects and *which* voxels are
  affected is **not disclosed** — you must find them from the data. A small multiplicative noise is
  present on every image and needs no special handling beyond the ordinary ratio.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `n_vox` and the filenames of the arrays below (with short ROI descriptions).
- `T1w.npy`, `T2w.npy` — the two coregistered weighted images, float32 `(n_vox,)`, in the
  subject's voxel order.
- `bias.npy` — the residual multiplicative bias field `rho` remaining in the ratio (`(n_vox,)`,
  1.0 = none).
- `tissue.npy` — per-voxel tissue label (`(n_vox,)`; see the protocol legend, white matter = 2).
- `mask.npy` — the brain mask (`(n_vox,)`; maps are graded over these voxels).
- `roi_high.npy`, `roi_low.npy` — the high-myelin and low-myelin landmark ROIs (`(n_vox,)`
  boolean masks) used for the affine calibration.

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **computable** map, each of shape `(n_vox,)` in the subject's voxel
order:
- `myelin_norm.npy` — the WM-referenced bias-corrected ratio (dimensionless).
- `myelin_cal.npy` — the 2-landmark affine-calibrated bias-corrected ratio (dimensionless) —
  **only where the two landmarks determine it**.

Do **not** write a file for a map the subject's data cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for the
maps you can produce so the rest of the cohort can be graded.
