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

Grading is **outcome-based and node-wise against the true bundle profile**: each profile you write
is compared node-by-node to the *true* along-tract mean of the anatomical bundle (the AFQ-style
profile of Yeatman et al. 2012). **Any scientifically valid estimator is accepted** — any trilinear
backend, any robust spatial-outlier prune — because the bundle-core scalar is flat over the core
(so the per-node mean is invariant to the averaging weights) and every correct method recovers the
same profile within tolerance. You are **not** required to reproduce any particular reference
implementation's output. Each (subject × scalar) is scored independently and partial results are
scored proportionally, so produce every profile you can and omit only what the data cannot support.

## Shared conventions and output contract (`/app/data/protocol.json`)
A single JSON with the conventions common to all subjects: the **coordinate convention** (the
affine maps voxel indices to world millimetres, `world = affine · [i,j,k,1]`; streamline vertices
are stored in the space named by each sidecar's `space` field — world mm or voxel index; the
reference centreline is always world mm), the **sampling** rule (trilinear interpolation of a
scalar volume, converting world→voxel via `inv(affine)`), the **node definition**
(nearest-reference-node assignment; a node's value is the mean over the bundle's streamlines of
each streamline's mean sample at that node), the **omit rule** (undeterminable nodes → NaN), and
the **output spec** and **units**. Read it before you start.

## Robustness / data-quality contract  (READ THIS)
The bundles are realistic, not clean:

- **Spurious off-core streamlines.** In a **majority of subjects, a few streamlines have strayed
  well out of the bundle core** (roughly 10 mm off, into low-FA / high-MD tissue) — gross spatial
  outliers. If they are included in the per-node mean they drag every node value toward background.
  **You must detect and prune such gross spatial-outlier streamlines before averaging** (any
  reasonable robust criterion works — they sit ~10 mm off a ~1 mm-wide core). *Which* subjects
  carry them and *which* streamlines they are is **not disclosed** — you must find them from the
  data. A small measurement noise is present on the scalar volumes and needs no special handling.

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
