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

Grading is **outcome-based and per wall node**: each map you write is recomputed from the
velocity field by a held-out reference and compared node-by-node. Partial cohorts and partial
map sets are scored proportionally, so produce every map you can support and omit the rest.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the conventions common to all subjects: the **velocity-field layout**, the
**geometry** (grid shape, voxel spacing, the provided lumen mask and the provided wall-node set
with their axis-aligned inward normals), the **WSS definition** (τ = viscosity × the wall-normal
gradient of the wall-**tangential** velocity, with the pinned `viscosity_pas` and the exact
cm/s·mm → Pa unit conversion), and the exact **output spec** (`tawss`, `wss_peak`, `osi`, with
OSI determinable only for a multi-frame 3-directional acquisition). Read it before you start.

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
