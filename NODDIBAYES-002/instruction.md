# Multi-fibre ball-and-stick reconstruction of a heterogeneous diffusion-MRI cohort

## Task
`/app/data/` holds a cohort of diffusion-MRI exams (`sub-01` … `sub-07`). Each subject was
scanned with a multi-shell or single-shell diffusion protocol. From each subject's signal,
reconstruct the per-voxel **crossing-fibre model** — how many fibre populations each voxel
holds, each fibre's **orientation**, and each fibre's **volume fraction** — using the
**ball-and-stick** model, and write the results out.

You must **infer the number of fibres per voxel** (0 for isotropic voxels, 1 for a single
coherent fibre, 2 for a crossing) rather than assume a fixed number: fit the isotropic,
one-stick and two-stick models and select between them by the model-selection rule defined in
the protocol, pruning any fibre the data do not support. There is no reference fitter provided —
implement the estimator yourself and get the model, the units, and the per-subject adaptation
right.

The cohort is **heterogeneous**: every subject's sidecar declares the shells it actually
acquired, and you must adapt the analysis per subject — a pipeline that assumes one fixed recipe
will not fit them all.

Grading is **outcome-based and voxelwise**: each map you write is recomputed from the signal by
a held-out reference and compared voxel-by-voxel inside the brain mask.

## Shared model and output contract (`/app/data/protocol.json`)
A single JSON with the model and conventions common to all subjects: the **ball-and-stick
signal model**, the **S0 normalisation** (mean of the b0 volumes), the **diffusivity
convention** (estimate `d` for multi-shell acquisitions; use the sidecar's pinned value for
single-shell), the **fibre-count model-selection rule** (the exact sum-of-squared-error criterion
that decides 0 vs 1 vs 2 fibres), the **estimator** (a deterministic bounded least-squares fit),
the **fibre ordering** (by decreasing volume fraction), and the **output specification**. Read
it before you start.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `n_vox`, `n_meas`, `shells`, `single_shell`, `fixed_diffusivity_mm2_s`, and
  the file names below.
- `dwi.npy` — the diffusion signal, a float32 array of shape `(n_meas, n_vox)` (one row per
  gradient volume, in the subject's voxel order).
- `bvals.npy` — the b-value of each volume (shape `(n_meas,)`, s/mm²; b0 volumes carry b≈0).
- `bvecs.npy` — the unit gradient direction of each volume (shape `(n_meas, 3)`; b0 volumes
  carry a zero vector).
- `mask.npy` — the brain mask (shape `(n_vox,)`; maps are graded over these voxels).

## Required outputs (`/app/output/sub-XX/`)
Write one file per map, in the subject's voxel order:
- `n_fibres.npy` — integer per voxel: the inferred number of fibres (0, 1 or 2).
- `f1.npy` — float32 `(n_vox,)`: the **primary** fibre volume fraction (0 where 0 fibres).
- `f2.npy` — float32 `(n_vox,)`: the **secondary** fibre volume fraction (0 where < 2 fibres).
- `v1.npy` — float32 `(n_vox, 3)`: the **primary** fibre unit orientation (zero where 0 fibres).
- `v2.npy` — float32 `(n_vox, 3)`: the **secondary** fibre unit orientation (zero where < 2
  fibres).

Fibres are ordered by decreasing volume fraction (fibre 1 = largest fraction).

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for
the maps you can produce so the rest of the cohort can be graded.
