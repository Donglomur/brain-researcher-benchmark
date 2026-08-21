# Relative pressure mapping from a heterogeneous 4D-flow / phase-contrast cohort

## Task
`/app/data/` holds a cohort of segmented-vessel flow exams (`sub-01` … `sub-08`). Each subject
provides the reconstructed blood **velocity field** over a regular voxel grid. From the velocity
field, compute the **relative static pressure** by pressure-Poisson (PPE) integration of the
Navier–Stokes momentum source, and write the results out.

The cohort is **heterogeneous**: every subject's sidecar declares the acquisition it actually
acquired (a 3-directional 4D-flow field vs a 2D through-plane phase-contrast plane), its frame
count, voxel spacing and frame spacing, and you must adapt the analysis per subject — **compute a
quantity only where the acquisition determines it; where it does not, omit it.** There is no
reference solver provided — implement the pressure reconstruction yourself and get the physics,
units, and per-subject adaptation right.

Grading is **outcome-based**: each quantity you write is recomputed from the velocity field by a
held-out reference and compared to it. Partial cohorts and partial quantity sets are scored
proportionally, so produce every quantity you can support and omit the rest.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the conventions common to all subjects: the **velocity-field layout**, the
**geometry** (grid shape, voxel spacing `dx_mm`, frame spacing `dt_ms`, the provided magnitude
and ROI — the vessel **lumen** is the high-signal region within the ROI), the **momentum source**
`b = -ρ(∂v/∂t + (v·∇)v) + μ∇²v` (temporal + convective + viscous, evaluated at the middle cardiac
frame), the **relative-pressure** definition (the PPE solution `∇²p = ∇·b` with the Neumann
boundary condition `∂p/∂n = b·n`, i.e. the least-squares integration of `∇p = b` over the lumen —
graded only **up to an additive constant**, so the gauge/reference-node choice does not matter),
the **peak drop** definition, the pinned constants (`ρ`, `μ`, and the Pa→mmHg conversion), the
**units**, and the exact **output spec**. Read it before you start.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `acquisition` (`"3d"` or `"tp"`), `grid_shape`, `n_vox`, `dx_mm`, `dt_ms`,
  `n_frames`, `n_comp`, `components`, `vessel_axis`, `venc_cms`, and the `vel_file`,
  `magnitude_file`, `roi_file`.
- `vel.npy` — float32, shape `(n_frames, n_comp, n_vox)`: the reconstructed velocity (cm/s), one
  cardiac frame per leading index, `n_comp` components (3-directional `[vx, vy, vz]` for a 4D-flow
  exam; a single through-plane component for a 2D exam), in the subject's voxel order.
- `magnitude.npy` — float32, shape `(n_vox,)` — the flow-compensated magnitude image.
- `roi.npy` — shape `(n_vox,)` — the analysis region; the vessel lumen is the high-signal region
  within it.

## Required outputs (`/app/output/sub-XX/`)
Write, in the subject's voxel order:
- `pressure.npy` — float32, shape `(n_vox,)` — the per-voxel **relative pressure** (mmHg). Graded
  over the interior-lumen voxels, up to an additive constant. **Only where determinable** (a
  3-directional 4D-flow acquisition).
- `peak_drop.npy` — float32, shape `(1,)` — the peak systolic **pressure drop** (mmHg) — for every
  subject.

Do **not** write `pressure.npy` for a subject whose acquisition cannot determine the spatial field.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid files for the
quantities you can produce so the rest of the cohort can be graded.
