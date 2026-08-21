# Time-dependent diffusion: restriction & structure from D(t)

## Task
`/app/data/` holds a cohort of time-dependent-diffusion exams (`sub-01` … `sub-08`). Each
subject provides a per-voxel **apparent diffusion coefficient** `D(t)` measured at one or more
**diffusion times** `t`. From the way `D` varies with `t`, estimate the per-voxel diffusion and
structural parameters the subject's sampling can support, and write them out.

The cohort is **heterogeneous**: each subject's sidecar declares the diffusion-time **regime** it
sampled (short-time, long-time, or a single time), and you must adapt the analysis per subject —
a pipeline that assumes one fixed recipe will not fit them all. **Estimate a quantity only where
the subject's diffusion-time sampling determines it; where it does not, omit it.**

Grading is **outcome-based and voxelwise**: each map you write is recomputed from `D(t)` by a
held-out reference and compared voxel-by-voxel inside the brain mask. Partial cohorts and partial
map sets are scored proportionally, so produce every map you can support and omit the rest.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the **short-time** law
(Mitra: `D(t) = D0·[1 − (4/(3·d·√π))·(S/V)·√(D0·t)]`, i.e. linear in `√t` with intercept the free
diffusivity `D0` and the surface-to-volume ratio `S/V` fixed by the slope and the dimension `d`),
the **long-time** law (`D(t) = D_inf + A·t^(−θ)`, i.e. linear in `t^(−θ)` with intercept the
tortuosity plateau `D_inf` and `θ` the structural-class exponent), the **fit convention** (ordinary
least squares of `D(t)` on the regime basis, each voxel independently), the reference diffusion
time `t_ref` and the definition of `Dref`, the **unit** of each quantity, and the **tissue legend**.
Read it before you start.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `regime` (`"short"`, `"long"`, or `"single"`), `times_ms` (the diffusion times),
  `n_vox`, and — where the regime needs them — `dimension` (short-time `d`) and `theta`
  (long-time `θ`, which varies across subjects).
- `Dt.npy` — a float32 array of shape `(n_times, n_vox)`: the apparent diffusion coefficient
  `D(t)` in µm²/ms, one row per diffusion time, in the subject's voxel order.
- `tissue.npy` — per-voxel tissue label (shape `(n_vox,)`; see the protocol legend).
- `mask.npy` — the brain mask (shape `(n_vox,)`; maps are graded over these voxels).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **determinable** map, each of shape `(n_vox,)` in the subject's voxel
order:
- `Dref.npy` — the diffusivity at the reference diffusion time `t_ref` (µm²/ms) — for **every**
  subject.
- `D0.npy` — the free / short-time diffusivity, the `√t → 0` intercept (µm²/ms) — **only where
  determinable**.
- `SV.npy` — the surface-to-volume ratio (1/µm) — **only where determinable**.
- `Dinf.npy` — the long-time plateau diffusivity, the `t → ∞` intercept (µm²/ms) — **only where
  determinable**.

Do **not** write a file for a map the subject's diffusion-time sampling cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for the
maps you can produce so the rest of the cohort can be graded.
