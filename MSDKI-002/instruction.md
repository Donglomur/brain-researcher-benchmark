# Mean-signal diffusion kurtosis (MSDKI) of a multi-shell cohort

## Task
`/app/data/` holds a cohort of multi-shell diffusion-MRI exams (`sub-01` … `sub-08`). From the
**powder-averaged (direction-averaged) signal per shell**, estimate the per-voxel **mean-signal
diffusivity (MSD)** and, where the acquisition determines it, the **mean-signal kurtosis (MSK)**,
and write them out.

The cohort is **heterogeneous**: each subject's b-value scheme differs, and a quantity is
defined only where the subject's shells constrain it — compute a quantity only where the
acquisition supports it and **omit** it otherwise. There is no reference fitter provided —
implement the estimators yourself and get the physics, units, and per-subject adaptation right.

Grading is **outcome-based and voxelwise**: each map you write is recomputed from the signals by
a held-out reference and compared voxel-by-voxel inside the brain mask.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the **powder-average**
definition, the **MSDKI signal model**, the **estimator**, the **unit** of each quantity, and
the **tissue legend**. Read it before you start. In brief:

- **Powder average.** Group the volumes into shells by b-value (`b=0` is its own shell). The
  powder-averaged signal of a shell is the **arithmetic mean over that shell's diffusion
  directions**, per voxel. MSDKI is defined on this direction-averaged signal.
- **Signal model** (per voxel): `Sbar(b) = S0 · exp( −b·MSD + (1/6)·b²·MSD²·MSK )`, with `b` in
  `ms/µm²` (`= bval[s/mm²] / 1000`), so **MSD is in µm²/ms**; **MSK is dimensionless**.
- **Estimator.** Fit by ordinary least squares on the natural log of the powder-averaged signal
  with design columns `[1, −b, b²/6]` over **all** of a subject's shells **including `b=0`**,
  giving `[ln S0, MSD, MSD²·MSK]`; then `MSK = (third coefficient) / MSD²`. With `b=0` plus a
  **single** non-zero shell only `[1, −b]` is determined (**MSD alone**); **MSK is then not
  computable and must be omitted**.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `n_vox`, `n_vol`, and the file names below.
- `dwi.npy` — float32 array of shape `(n_vol, n_vox)`: the diffusion signal, one row per volume,
  in the subject's voxel order.
- `bvals.npy` — shape `(n_vol,)`, the b-value of each volume in **s/mm²** (`0` = b=0).
- `bvecs.npy` — shape `(n_vol, 3)`, the diffusion-encoding directions (unit vectors; `0` for b=0).
- `mask.npy` — the brain mask (shape `(n_vox,)`; maps are graded over these voxels).
- `tissue.npy` — per-voxel tissue label (shape `(n_vox,)`; see the protocol legend, white
  matter = 2).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **computable** map, each of shape `(n_vox,)` in the subject's voxel
order:
- `MSD.npy` — mean-signal diffusivity (µm²/ms).
- `MSK.npy` — mean-signal kurtosis (dimensionless) — **only where determinable**.

Do **not** write a file for a map the subject's acquisition cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for the
maps you can produce so the rest of the cohort can be graded.
