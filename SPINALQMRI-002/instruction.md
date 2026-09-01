# Per-level quantitative MRI of a heterogeneous spinal-cord cohort

## Task
`/app/data/` holds a cohort of cervical spinal-cord quantitative-MRI exams
(`sub-01` … `sub-08`). Each subject is a stack of axial slices, one per vertebral level. From
the acquired contrasts, estimate the per-voxel **quantitative cord maps** and the **per-level
cord means**, and write them out.

The cohort is **heterogeneous**: every subject's sidecar declares the vertebral levels it
covers and the contrasts it actually acquired, and you must adapt the analysis per subject — a
pipeline that assumes one fixed recipe will not fit them all. **Compute a map only where the
subject's acquisition determines it; where it does not, omit that map.** No fitter is provided —
implement the estimators yourself and get the physics, units, and per-subject adaptation right.

Grading is **outcome-based against the true underlying physiology**: each map you write is
compared, inside the cord ROI, to the *true* per-voxel MTR (p.u.) and R1 (1/s) that generated
the images. **Any scientifically valid estimator is accepted** — any robust outlier rule, any
linear algebra — because every correct method recovers the same physiology within tolerance.
You are **not** required to reproduce any particular reference implementation's output. Partial
cohorts and partial map sets are scored proportionally, so produce every map you can support and
omit the rest.

## Robustness / data-quality contract  (READ THIS)
The provided cord segmentation is an **ROI, not a guarantee**, and the images are realistic, not
clean. Handle all of the following robustly; *which* levels and *which* voxels are affected is
**not disclosed** — you must find them from the data:

- **CSF partial-volume over-inclusion.** On a **majority of levels**, the cord ROI
  (`cord_mask.npy`) **over-includes** a few free-water / CSF voxels at the cord boundary; their
  quantitative value collapses toward CSF (MTR toward zero, R1 far below cord). **Detect and
  exclude** such voxels (write them `NaN` in the per-voxel map and drop them from the per-level
  mean).
- **Gross cord-motion / CSF-pulsation voxels.** A **subset of levels** additionally carry a few
  true-cord voxels whose signal is thrown grossly off by motion / pulsation (value far from the
  clean-cord cluster). **Detect and exclude** these too. Any reasonable robust rule (a per-level
  MAD / z outlier test on the quantitative value, etc.) removes the same voxels — the
  contamination is gross, a wide gap from the tight clean-cord distribution.
- **B1+ transmit inhomogeneity (VFA/R1).** VFA subjects ship a per-voxel transmit map
  (`b1.npy`), uniform on some subjects and ±25 % inhomogeneous on others. The true flip is
  `a = B1 × radians(flip_deg)`; ignoring it biases R1.

Modest Rician noise is present on every image and does **not** need special handling beyond an
ordinary estimate.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the conventions common to all subjects: the **MTR** definition, the **R1**
variable-flip-angle solve, the **B1+ convention** (`a = B1 × radians(flip_deg)`), the **unit**
of each quantity, and the cord-ROI and output specification. Read it before you start.

- **MTR** (magnetization-transfer ratio, per cent units) = `100 × (S_off − S_on) / S_off` per
  voxel, where `S_off` is the MT-pulse-off image and `S_on` the MT-pulse-on image.
- **R1** (1/s) is the two-flip variable-flip-angle (DESPOT1) solve at a common TR: with
  `y = S/sin(a)` and `x = S/tan(a)`, the two flips give `E1 = (y_hi − y_lo)/(x_hi − x_lo)` and
  `R1 = −ln(E1)/TR`, with the true per-voxel flip `a = B1 × radians(flip_deg)`.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `levels` (the vertebral-level labels, in order), `vox_per_level`,
  `grid` (`[H, W]` of each axial slice, row-major), `tr_ms`, and a `contrasts` block declaring
  which of the MT pair (`mt_off`, `mt_on`) and the two-flip VFA pair (`fa_lo`, `fa_hi`, with
  `flip_lo_deg`, `flip_hi_deg`, and `b1_file`) are `present`, with their file names.
- each contrast `<name>.npy` — a float32 array of shape `(n_levels, vox_per_level)`.
- `cord_mask.npy` — the per-level cord region of interest, shape `(n_levels, vox_per_level)`
  (bool). Maps are graded over these cord voxels.
- `b1.npy` (when a VFA pair is present) — the per-voxel transmit factor (1.0 = nominal), shape
  `(n_levels, vox_per_level)`.

## Required outputs (`/app/output/sub-XX/`)
For each **computable** map write, in float32:
- `MTR_vox.npy`, `MTR_level.npy` — only if the MT pair was acquired.
- `R1_vox.npy`, `R1_level.npy` — only if the VFA pair was acquired.

`*_vox.npy` has shape `(n_levels, vox_per_level)`: report a finite value on each cord voxel that
supports a **reliable** estimate, and `NaN` on any cord voxel you exclude (and anywhere outside
the cord ROI). `*_level.npy` has shape `(n_levels,)` in sidecar level order: the cord mean over
the voxels you kept at each level.

Do **not** write a file for a map the subject's acquisition cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for
the maps you can produce so the rest of the cohort can be graded.
