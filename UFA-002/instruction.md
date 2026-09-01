# Microscopic anisotropy (uFA) from a heterogeneous b-tensor-encoding cohort

## Task
`/app/data/` holds a cohort of diffusion exams (`sub-01` … `sub-08`) acquired with **b-tensor
encoding** — each subject was scanned with one or more b-tensor **shapes** (linear LTE, planar
PTE, and/or spherical STE) over a set of b-values. From the direction-averaged (powder)
signals, estimate the per-voxel **quantitative diffusion maps** and write them out.

The cohort is **heterogeneous**: every subject's sidecar declares, per acquired volume, the
b-tensor shape and b-value it actually used, and you must adapt the analysis per subject — a
pipeline that assumes one fixed encoding set will not fit them all. **Compute a map only where
the subject's acquired encoding set determines it; where it does not, omit that map.** There is
no reference fitter provided — implement the estimators yourself and get the physics, units, and
per-subject adaptation right.

Grading is **outcome-based and voxelwise against the true underlying physiology**: each map you
write is compared voxel-by-voxel to the *true* quantitative map that generated the powder signals
(the tensor-valued encoding model of Westin et al. 2016 / Lasič et al. 2014). **Any scientifically
valid estimator is accepted** — any robust gross-volume rejection, any ordinary-least-squares
assembly of the shared-MD joint powder fit, any equivalent `V_iso`/`V_aniso` solve — because every
correct method recovers the same physical quantities within tolerance. You are **not** required to
reproduce any particular reference implementation's output. Partial cohorts and partial map sets
are scored proportionally, so produce every map you can support and omit the rest. MD and Ciso are
graded over the whole brain mask; **uFA is graded over brain parenchyma (grey + white matter)** —
microscopic FA is defined where microscopic anisotropy exists, and in free-water CSF it is ≈ 0 and
ill-conditioned (still write a full-length map; the CSF voxels simply are not graded for uFA).

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the b-tensor **encoding
convention** (the normalised anisotropy `b_Delta`: LTE `+1`, PTE `-1/2`, STE `0`), the powder
**signal model** and the shared/​per-shape parameter structure, and the exact definitions of
**MD**, **uFA**, and **Ciso**, the **unit** of each quantity, and the **tissue legend**. Read it
before you start. In brief:

- Powder (direction-averaged) signal of a `(shape, b)` shell = the arithmetic mean of that
  shell's volumes, modelled as
  `Sbar_s(b) = S0 · exp(-b·MD + ½·b²·C2_s)` with `C2_s = V_iso + (4/5)·b_Delta(s)²·V_aniso`.
  `S0` (b=0) and `MD` (the b¹ coefficient) are **shared across all shapes**; only the curvature
  `C2_s` depends on shape. Fit in the log domain.
- **MD** (mean diffusivity, µm²/ms) — the shared linear coefficient; determinable for every subject.
- **uFA** (microscopic FA, dimensionless in `[0,1]`) —
  `uFA = sqrt( 3·V_aniso / (2·V_aniso + V_iso + MD²) )`, clamped to `[0,1]`, with `V_iso`,
  `V_aniso` recovered from the per-shape curvatures. Determinable only where `V_aniso` is
  identifiable.
- **Ciso** (isotropic-heterogeneity index, dimensionless) — `V_iso / MD²`. Determinable only
  where `V_iso` is identifiable.

## Robustness / data-quality contract  (READ THIS)
The signals are realistic, not clean:

- **Grossly corrupted volumes.** In a **majority of subjects, one or two individual
  diffusion-weighted volumes are grossly corrupted** (motion signal-dropout / spike) and are
  physically inconsistent with the powder decay of the rest of that subject's acquisition. **You
  must detect and reject such corrupted volumes robustly before the joint powder fit**, or the
  shared MD and the per-shape curvatures — and every downstream map (uFA, Ciso) — are biased.
  *Which* subjects and *which* volumes are affected is **not disclosed** — you must find them from
  the data. Any scientifically valid robust scheme is acceptable (robust regression, outlier
  rejection on the log-signal residuals, etc.); a non-robust fit over all volumes recovers the
  wrong maps on the affected subjects and fails those panels. Modest Rician noise is present on
  every volume and needs no special handling beyond an ordinary fit.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `n_vox`, `n_vol`, the list `shapes` of distinct b-tensor shapes acquired,
  and `volumes`: one entry per row of `dwi.npy`, giving that volume's `shape` (`"b0"` for the
  non-diffusion-weighted volumes) and `b` (b-value, ms/µm²).
- `dwi.npy` — a float32 array of shape `(n_vol, n_vox)`: one row per acquired volume, in the
  subject's voxel order.
- `mask.npy` — the brain mask (shape `(n_vox,)`; maps are graded over these voxels).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **determinable** map, each of shape `(n_vox,)` in the subject's
voxel order:
- `MD.npy` — mean diffusivity (µm²/ms).
- `uFA.npy` — microscopic fractional anisotropy (dimensionless) — **only where determinable**.
- `Ciso.npy` — isotropic-heterogeneity index (dimensionless) — **only where determinable**.

Do **not** write a file for a map the subject's encoding set cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for
the maps you can produce so the rest of the cohort can be graded.
