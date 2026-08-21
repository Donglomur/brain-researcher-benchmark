# Soma-and-neurite (SANDI) microstructure of a heterogeneous diffusion-MRI cohort

## Task
`/app/data/` holds a cohort of multi-shell spherical-mean diffusion-MRI exams
(`sub-01` … `sub-08`). Each subject was scanned with several b=0 volumes and, per diffusion
shell, several gradient-direction volumes. From these signals, estimate the per-voxel
**soma-and-neurite (SANDI) compartment maps** and write them out.

The cohort is **heterogeneous**: every subject's sidecar declares the shells it actually
acquired (b-value, gradient pulse timing `small_delta`/`big_delta`, number of directions), and
you must adapt the analysis per subject — a pipeline that assumes one fixed acquisition scheme
will not fit them all. **Compute a quantity only where the subject's acquisition determines it;
where it does not, omit that map.** There is no reference fitter provided — implement the
estimators yourself and get the physics, units, and per-subject adaptation right.

Grading is **outcome-based and voxelwise**: each map you write is recomputed from the signals
by a held-out reference and compared voxel-by-voxel inside the brain mask. Partial cohorts and
partial map sets are scored proportionally, so produce every map you can support and omit the
rest.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the **spherical-mean
signal model** (a b=0-normalised sum of a neurite *stick*, a soma *sphere*, and an
extra-cellular *ball*, whose weights are the b=0 signal fractions and sum to 1), the exact
**compartment kernels** (including the restricted-sphere Gaussian-phase kernel and how its
gradient strength follows from each shell's `(b, small_delta, big_delta)`), the fixed
intrinsic diffusivity `d_intra_um2_ms`, the **determinability rule** (when the soma
compartment — `f_soma` and `R_s` — is resolvable), the **units** of each quantity, and the
tissue legend. Read it before you start.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `n_vox` and a `shells` list; each shell gives `b_s_mm2`, `small_delta_ms`,
  `big_delta_ms`, and `n_dirs`. The `dwi` volumes are stored shell-by-shell in this order (the
  b=0 block first, then each shell's directions); split them by the cumulative `n_dirs`.
- `dwi.npy` — a float32 array of shape `(n_vol, n_vox)`: the diffusion-weighted magnitude
  signal, one row per acquired volume, in the subject's voxel order.
- `bvals.npy` — the b-value (s/mm²) of each volume, shape `(n_vol,)`.
- `bvecs.npy` — the gradient direction of each volume, shape `(n_vol, 3)`.
- `tissue.npy` — per-voxel tissue label (shape `(n_vox,)`; see the protocol legend).
- `mask.npy` — the brain mask (shape `(n_vox,)`; maps are graded over these voxels).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **computable** map, each of shape `(n_vox,)` in the subject's
voxel order:
- `f_neurite.npy` — neurite (intra-stick) signal fraction (dimensionless).
- `f_extra.npy` — extra-cellular (ball) signal fraction (dimensionless).
- `f_soma.npy` — soma (sphere) signal fraction — **only where determinable**.
- `R_s.npy` — soma radius (µm) — **only where determinable**.

Do **not** write a file for a map the subject's acquisition cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for
the maps you can produce so the rest of the cohort can be graded.
