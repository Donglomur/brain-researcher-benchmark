# Mean-kurtosis decomposition from a tensor-valued diffusion-encoding cohort

## Task
`/app/data/` holds a cohort of diffusion exams (`sub-01` … `sub-08`) acquired with **b-tensor
encoding** — each subject was scanned with one or more b-tensor **shapes** (linear LTE, planar
PTE, and/or spherical STE) over a set of b-values. From the direction-averaged (powder) signals,
estimate the per-voxel **mean-kurtosis decomposition** and **microscopic FA**, and write them out.

The cohort is **heterogeneous**: every subject's sidecar declares, per acquired volume, the
b-tensor shape and b-value it actually used, and you must adapt the analysis per subject — a
pipeline that assumes one fixed encoding set will not fit them all. **Compute a map only where the
subject's acquired encoding set determines it; where it does not, omit that map.** There is no
reference fitter provided — implement the estimators yourself and get the physics, units, and
per-subject adaptation right.

Grading is **outcome-based and voxelwise**: each map you write is recomputed from the signals by a
held-out reference and compared voxel-by-voxel inside the brain mask. Each (subject, map) is scored
on its own, so produce every map a subject supports and omit the rest.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the b-tensor **encoding
convention** (the normalised anisotropy `b_Delta`: LTE `+1`, PTE `-1/2`, STE `0`), the powder
**signal model**, and the exact definitions and **units** of **MD**, **MK**, **MKi**, **MKa**, and
**microFA**, plus the **tissue legend**. Read it before you start. In brief:

- Powder (direction-averaged) signal of a `(shape, b)` shell = the arithmetic mean of that shell's
  volumes, modelled as
  `Sbar_s(b) = S0 · exp(-b·MD + ½·b²·C2_s)` with `C2_s = V_iso + (4/5)·b_Delta(s)²·V_aniso`.
  `S0` (b=0) and `MD` (the b¹ coefficient) are **shared across all shapes**; only the curvature
  `C2_s` depends on shape. `V_iso` is the isotropic diffusion-variance and `V_aniso` the
  anisotropic (microscopic-anisotropy) diffusion-variance. Fit in the log domain.
- **MD** (mean diffusivity, µm²/ms) — the shared linear coefficient; determinable for every subject.
- **MKi** (isotropic mean kurtosis, dimensionless) — `MKi = 3·V_iso/MD²`. Determinable where
  `V_iso` is identifiable.
- **MKa** (anisotropic mean kurtosis, dimensionless) — `MKa = (12/5)·V_aniso/MD²`. Determinable
  where `V_aniso` is identifiable.
- **MK** (total mean kurtosis, dimensionless) — `MK = 3·C2_LTE/MD²`, the mean kurtosis of the
  linear (LTE) powder decay (equivalently `MK = MKi + MKa`). Report it wherever LTE encoding is
  acquired.
- **microFA** (microscopic FA, dimensionless in `[0,1]`) —
  `microFA = sqrt( (3/2)·V_aniso / (V_aniso + V_iso + MD²) )`, clamped to `[0,1]`. Determinable
  where both variances are identifiable.

`V_iso`, `V_aniso` are recovered from the per-shape curvatures via
`C2_s = V_iso + (4/5)·b_Delta(s)²·V_aniso`.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `n_vox`, `n_vol`, the list `shapes` of distinct b-tensor shapes acquired, and
  `volumes`: one entry per row of `dwi.npy`, giving that volume's `shape` (`"b0"` for the
  non-diffusion-weighted volumes) and `b` (b-value, ms/µm²).
- `dwi.npy` — a float32 array of shape `(n_vol, n_vox)`: one row per acquired volume, in the
  subject's voxel order.
- `mask.npy` — the brain mask (shape `(n_vox,)`; maps are graded over these voxels).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **determinable** map, each of shape `(n_vox,)` in the subject's voxel
order:
- `MD.npy` — mean diffusivity (µm²/ms).
- `MK.npy` — total mean kurtosis — **only where determinable**.
- `MKi.npy` — isotropic mean kurtosis — **only where determinable**.
- `MKa.npy` — anisotropic mean kurtosis — **only where determinable**.
- `microFA.npy` — microscopic FA — **only where determinable**.

Do **not** write a file for a map the subject's encoding set cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for the
maps you can produce so the rest of the cohort can be graded.
