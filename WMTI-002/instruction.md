# White-matter-tract-integrity mapping of a heterogeneous diffusion-kurtosis cohort

## Task
`/app/data/` holds a cohort of diffusion-weighted exams (`sub-01` … `sub-08`). Each subject was
scanned with a set of diffusion gradients over one or more b-value shells. From these signals,
estimate the per-voxel **White-Matter-Tract-Integrity (WMTI)** parameters of the two-compartment
model (Fieremans et al., NeuroImage 2011) and write them out.

The cohort is **heterogeneous**: every subject's sidecar declares the b-values and gradient
directions it actually acquired, and you must adapt the analysis per subject — a pipeline that
assumes one fixed recipe will not fit them all. **Compute a map only where the subject's
acquisition and the model determine it; where they do not, omit it.** There is no reference
fitter provided — implement the estimators yourself and get the physics, units, and per-subject
adaptation right.

Grading is **outcome-based and voxelwise**: each map you write is recomputed from the signals by
a held-out reference and compared voxel-by-voxel inside the brain mask. Partial cohorts and
partial map sets are scored proportionally, so produce every map you can support and omit the
rest.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the **DKI signal model**
(the diffusion tensor `D` and kurtosis tensor `W` from `ln S(b,g) = ln S0 - b·D_app(g) +
(1/6)·b²·Dbar²·W_app(g)`), the requirement that both tensors are identifiable only with **at
least two distinct non-zero b-shells**, the **WMTI definitions** (`AWF`, `Da`, `De_par`,
`De_perp`, `tortuosity`) in the diffusion-tensor eigenframe with the exact branch and the
`AWF = Kmax/(Kmax+3)` convention, the **validity domain** of the two-compartment model, the
**unit** of each quantity, and the tissue conventions. Read it before you start.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `n_vox`, `n_vol`, and the file names below.
- `dwi.npy` — the diffusion signal, a float32 array of shape `(n_vol, n_vox)`: one row per
  acquired volume, in the subject's voxel order.
- `bvals.npy` — `(n_vol,)` b-values in s/mm² (b≈0 volumes are the non-diffusion-weighted
  references).
- `bvecs.npy` — `(n_vol, 3)` unit gradient directions (the b≈0 rows are zero).
- `mask.npy` — the brain mask (`(n_vox,)`; maps are graded over these voxels).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **computable** WMTI map, each of shape `(n_vox,)` in the subject's
voxel order, with diffusivities in **µm²/ms**:
- `AWF.npy` — axonal water fraction (dimensionless, in [0,1]).
- `Da.npy` — intra-axonal (axonal) diffusivity.
- `De_par.npy` — extra-axonal axial diffusivity.
- `De_perp.npy` — extra-axonal radial diffusivity.
- `tortuosity.npy` — `De_par / De_perp` (dimensionless).

Set voxels where the two-compartment WMTI model is **invalid** to a non-finite value (NaN). If a
subject's acquisition cannot support WMTI **at all**, do **not** write any of its maps.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for the
subjects and maps you can produce so the rest of the cohort can be graded.
