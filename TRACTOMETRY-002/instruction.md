# Along-tract quantitative profiling of a heterogeneous fibre-bundle cohort

## Task
`/app/data/` holds a diffusion cohort (`sub-01` … `sub-08`). Each subject provides one
white-matter fibre **bundle** (a set of streamlines), an **FA** and an **MD** scalar volume, the
voxel→world **affine**, and a shared **reference centreline** of `N` ordered nodes. For every
subject, produce the along-tract **profile** of each scalar: the bundle's mean FA and mean MD
**at each reference node**.

The cohort is **heterogeneous**: each subject's sidecar declares how that subject is stored and
what its bundle covers, and you must adapt per subject — a pipeline that assumes one fixed recipe
will not fit them all. **Report a node only where the bundle determines it; where it does not,
omit that node.** There is no profiling tool provided — implement it yourself and get the
coordinate handling, sampling, node correspondence, and per-subject adaptation right.

Grading is **outcome-based and node-wise**: each profile you write is recomputed from the
streamlines and volumes by a held-out reference and compared node-by-node. Each (subject × scalar)
is scored independently and partial results are scored proportionally, so produce every profile
you can and omit only what the data cannot support.

## Shared conventions and output contract (`/app/data/protocol.json`)
A single JSON with the conventions common to all subjects: the **coordinate convention** (the
affine maps voxel indices to world millimetres, `world = affine · [i,j,k,1]`; streamline vertices
are stored in the space named by each sidecar's `space` field — world mm or voxel index; the
reference centreline is always world mm), the **sampling** rule (trilinear interpolation of a
scalar volume, converting world→voxel via `inv(affine)`), the **node definition**
(nearest-reference-node assignment; a node's value is the mean over the bundle's streamlines of
each streamline's mean sample at that node), the **omit rule** (undeterminable nodes → NaN), and
the **output spec** and **units**. Read it before you start.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `space` (`"world"` or `"voxel"`), `n_nodes`, `n_streamlines`, `voxel_size`,
  `volume_shape`, and the file names below.
- `fa.npy`, `md.npy` — the FA (dimensionless) and MD (mm²/s) scalar volumes, shape `volume_shape`.
- `affine.npy` — the 4×4 voxel→world affine.
- `reference.npy` — the reference centreline, shape `(n_nodes, 3)`, world mm, node 0 first.
- `streamlines.npy` — all streamline vertices concatenated, shape `(total_vertices, 3)`, in the
  subject's declared `space`.
- `offsets.npy` — `int` array of length `n_streamlines + 1`; streamline `k` is
  `streamlines[offsets[k] : offsets[k+1]]`.

## Required outputs (`/app/output/sub-XX/`)
Write, per subject, two float32 `.npy` arrays of shape `(n_nodes,)` in reference-node order:
- `FA_profile.npy` — the mean FA at each node.
- `MD_profile.npy` — the mean MD at each node (mm²/s).

Determinable nodes hold the mean; **undeterminable nodes hold `NaN`**. The determinable segment
differs per subject and must be read off the data.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for the
subjects you can produce so the rest of the cohort can be graded.
