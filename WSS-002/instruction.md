# Wall shear stress from a heterogeneous 4D-flow / phase-contrast cohort

## Task
`/app/data/` holds a cohort of segmented-vessel flow exams (`sub-01` … `sub-08`). Each subject
is a straight vessel (square cross-section, axis = z) sampled on a regular 3D grid, with the
reconstructed blood **velocity field** provided. From the velocity field, compute the
**near-wall velocity gradient** at each vessel-wall node, form the **wall shear stress**, and
write the results out.

The cohort is **heterogeneous**: every subject's sidecar declares the velocity encoding it
actually acquired (3-directional 4D-flow vs 2D through-plane phase-contrast), its frame count,
voxel spacing and VENC, and you must adapt the analysis per subject — **compute a quantity only
where the acquisition determines it; where it does not, omit it.** There is no reference tool
provided — implement the wall-shear computation yourself and get the physics, units, and
per-subject adaptation right.

Grading is **outcome-based and per wall node against the true underlying physiology**: each map
you write is compared node-by-node to the *true* wall-shear-stress quantity that the velocity
field encodes. **Any scientifically valid estimator is accepted** — any background fit, any
high-breakdown near-wall gradient estimator — because every correct method recovers the same
physical quantity within tolerance; you are **not** required to reproduce any particular reference
implementation's output. Partial cohorts and partial map sets are scored proportionally, so
produce every map you can support and omit the rest.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the conventions common to all subjects: the **velocity-field layout**, the
**geometry** (grid shape, voxel spacing, the provided lumen mask and the provided wall-node set
with their axis-aligned inward normals), the **WSS definition** (τ = viscosity × the wall-normal
gradient of the wall-**tangential** velocity, with the pinned `viscosity_pas` and the exact
cm/s·mm → Pa unit conversion), and the exact **output spec** (`tawss`, `wss_peak`, `osi`, with
OSI determinable only for a multi-frame 3-directional acquisition). Read it before you start.

## Robustness / data-quality contract  (READ THIS)
The velocity field is realistic, not clean:

- **Background / eddy-current offset.** In a **majority of subjects** the reconstructed velocity
  carries a smooth first-order (linear) spatial **background offset** (eddy-current phase) added
  to every component. **You must estimate it from the STATIC (non-lumen) tissue and subtract it**
  before the near-wall gradient — the static tissue has zero true velocity, so a plane fit there
  recovers the offset; left in, it biases the wall-normal gradient. It is a no-op on the subjects
  that have none.
- **Grossly corrupted near-wall voxels.** The outermost lumen voxel along each inward normal is
  grossly **partial-volume** biased, and on a minority of subjects a few near-wall voxels are
  **phase-wrap aliased** (velocity off by ±2·VENC). These are physically inconsistent with the
  linear near-wall profile and **must be rejected** — use a **high-breakdown** near-wall gradient
  estimator (e.g. Theil–Sen / repeated-median, or explicit outlier rejection) that tolerates up
  to a couple of gross outliers among the near-wall samples. *Which* subjects/voxels are affected
  is **not disclosed**; any scientifically valid robust scheme is acceptable. A naive stencil that
  uses the corrupted voxels recovers the wrong gradient and fails those nodes.

Modest velocity noise is present and does **not** need special handling beyond the ordinary
near-wall fit.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `acquisition` (`"3dir"` or `"tp"`), `grid_shape` (`[nz,ny,nx]`, C-order),
  `n_vox`, `dx_mm`, `n_frames`, `n_comp`, `components` (e.g. `["vx","vy","vz"]` or `["vz"]`, with
  `vz` the axial/through-plane component), `venc_cms`, and the file names below.
- `vel.npy` — float32 `(n_frames, n_comp, n_vox)`: the reconstructed velocity (cm/s), one
  cardiac frame per row, the components named by `components`, in the subject's voxel order
  (reshape a spatial array to `grid_shape`, C-order).
- `mask.npy` — the lumen mask (`(n_vox,)`, 1 = lumen).
- `wall_index.npy` — `(n_wall,)` int flat voxel indices of the graded wall nodes.
- `wall_normal.npy` — `(n_wall, 3)` float inward unit normals `[x,y,z]` at those nodes.

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **computable** map, each of shape `(n_wall,)` aligned to
`wall_index.npy` order:
- `tawss.npy` — time-averaged WSS magnitude (mean over frames of |τ|, Pa).
- `wss_peak.npy` — peak WSS magnitude (max over frames of |τ|, Pa).
- `osi.npy` — oscillatory shear index, `0.5·(1 − |Σ_frames τ| / Σ_frames |τ|)` (dimensionless) —
  **only where determinable**.

Do **not** write a file for a map the subject's acquisition cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for
the maps you can produce so the rest of the cohort can be graded.
