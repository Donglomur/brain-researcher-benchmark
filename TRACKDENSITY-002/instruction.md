# Track-density imaging (TDI) of a heterogeneous tractography cohort

## Task
`/app/data/` holds a cohort of whole-brain tractography exams (`sub-01` … `sub-08`). Each
subject provides a set of streamlines (fibre trajectories). From these streamlines, compute the
per-cell **track-density image(s)** — the number of streamlines passing through each grid cell —
and write them out.

The cohort is **heterogeneous**: tractograms differ in size, voxel grid and world placement, and
not every subject's tractogram supports every map — **compute a map only where the subject's
tractogram determines it, and omit it otherwise** (see the support rule below).

Grading is **outcome-based and cellwise**: each map you write is recomputed from the streamlines
by a held-out reference and compared cell-by-cell. Partial cohorts and partial map sets are
scored proportionally, so produce every map you can support and omit the rest.

## Shared conventions and output contract (`/app/data/protocol.json`)
A single JSON with the conventions common to all subjects: the streamline **storage format**, the
**track-density definition** (segment-intersection count), the **grid/affine convention**, the
**super-resolution** grid definition, the **support rule** (when the super-resolution map is
determinable), the **unit** of each quantity, and the output spec. Read it before you start. In
particular:

- **Track density of a cell** = the number of *distinct* streamlines whose polyline passes
  through that cell. A streamline is the piece-wise-linear path through its stored vertices
  (the polyline itself — do not resample or smooth it); it contributes **+1** to a cell if any
  part of that path lies inside the cell, counted **at most once per cell** no matter how many
  times it enters. Count the **full sub-voxel path** of every segment — not merely the cells
  that happen to contain a stored vertex.
- **Grid / affine** — the sidecar's `affine` (4×4) maps continuous voxel coordinates to world
  millimetres (`world = affine @ [i,j,k,1]`), so voxel coordinates = `inv(affine) @ [x,y,z,1]`;
  a continuous voxel coordinate `u` lies in cell `floor(u)` and integer cell `n` spans `[n, n+1)`.
- **Super-resolution** — the super-resolution map is on a grid `super_factor` times finer along
  every axis, sharing the native grid's world corner and orientation: super voxel coordinates =
  native voxel coordinates × `super_factor`, and its shape is `native_shape × super_factor`.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `n_streamlines`, `affine`, `native_shape` (nx,ny,nz), `voxel_size_mm`,
  `super_factor`, and the names of the two array files below.
- `streamlines.npy` — a float32 array of shape `(P, 3)`: **all** streamline vertices, in world
  millimetres, concatenated end-to-end.
- `offsets.npy` — an int64 array of length `n_streamlines + 1`: streamline `k` is
  `streamlines[offsets[k] : offsets[k+1]]` (CSR layout).

## Support rule (which maps to produce)
- `tdi_native` — the native-grid track density — is produced for **every** subject.
- `tdi_super` — the super-resolution track density — is determinable **only** for a subject whose
  tractogram is dense enough (at least `n_min` streamlines, given in the protocol). A sparser
  tractogram cannot populate the finer grid, so for those subjects `tdi_super` must be **omitted**
  (write no file).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **computable** map:
- `tdi_native.npy` — native-grid track-density counts, shape `native_shape`.
- `tdi_super.npy` — super-resolution track-density counts, shape `native_shape × super_factor`
  — **only where determinable**.

Do **not** write a file for a map the subject's tractogram cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for the
maps you can produce so the rest of the cohort can be graded.
