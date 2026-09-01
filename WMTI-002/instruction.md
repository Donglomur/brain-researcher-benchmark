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

Grading is **outcome-based and voxelwise against the true underlying physiology**: each map you
write is compared voxel-by-voxel, inside the brain mask, to the *true* WMTI parameter map that
generated the signals. **Any scientifically valid estimator is accepted** — weighted or ordinary
least squares, sphere-maximum or analytic radial kurtosis, any robust gross-volume rejection —
because every correct method recovers the same physiology within tolerance; you are **not**
required to reproduce any particular reference implementation's output. Partial cohorts and
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

## Robustness / data-quality contract  (READ THIS)
The signals are realistic, not clean:

- **Grossly corrupted diffusion volumes.** In a **majority of the multi-shell subjects, one to
  three individual diffusion volumes are grossly corrupted** (signal dropout / spike scaling a
  whole volume) and are physically inconsistent with the mono-/bi-exponential decay of the rest
  of the acquisition. **You must detect and reject such corrupted volumes robustly before the
  DKI tensor fit** — an un-rejected volume biases the log-linear fit and therefore every WMTI
  parameter. *Which* subjects and *which* volumes are affected is **not disclosed** — you must
  find them from the data. Any scientifically valid robust scheme is acceptable (outlier
  rejection on the whole-volume log-residual, robust regression, etc.); a plain fit over all
  volumes recovers the wrong tensors on the affected subjects and fails those panels. The
  corruptions are gross (far larger than the ordinary noise), so a wide robust margin rejects
  them without dropping any legitimate volume.
- **Validity domain (declared in the protocol).** The two-compartment WMTI model holds only in
  coherent, highly-anisotropic single-fibre white matter; in low-anisotropy voxels (grey matter,
  CSF, partial volume) the model is invalid and every WMTI parameter is **undefined** there —
  leave those voxels non-finite (NaN).

Modest Gaussian noise is present on every volume and does **not** need special handling beyond
the ordinary fit.

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
