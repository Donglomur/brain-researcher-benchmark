# Shear-wave elastography of a heterogeneous ultrafast-imaging cohort

## Task
`/app/data/` holds a cohort of ultrafast shear-wave-elastography exams (`sub-01` … `sub-09`).
In each exam, one or more acoustic-radiation-force **pushes** launch a transient shear wave
that propagates laterally through the tissue, and the tissue **particle velocity** `v(z, x, t)`
is tracked frame-by-frame across a 2-D imaging plane. From the tracked wave, estimate the
per-region shear-wave speed, convert it to a **Young's-modulus map**, and write it out.

The cohort is **heterogeneous**: each subject's sidecar declares its frame rate, its pixel
geometry, and the pushes it actually fired (with their lateral origins), and which regions a
given push can measure differs across the cohort — adapt the analysis per subject rather than
assuming one fixed recipe. **Estimate a region's modulus only where this subject's data
reliably determine it; where they do not, leave it out.** There is no reference estimator
provided — implement the inversion yourself and get the physics, units, and per-subject
adaptation right.

Grading is **outcome-based and voxelwise**: each map you write is recomputed from the velocity
movies by a held-out reference and compared pixel-by-pixel over the in-field pixels. Partial
cohorts and partial maps are scored proportionally, so produce every map you can support.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the **speed estimator**
(shear-wave speed `c` from the laterally-adjacent time-of-flight — cross-correlate adjacent
traces for the propagation delay `tau`, `c = dx / tau`, with `dx` the lateral pitch and a
frame-delay converted to seconds via the subject's `dt = 1/frame_rate_hz`), the **modulus
convention** (`E = 3·rho·c²` with `rho = 1000 kg/m³`, reported in **kPa**), the definition and
determinability of the **reliability** map, the **unit** of each quantity, and the **region
legend**. Read it before you start.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `frame_rate_hz`, `dx_m`, `dz_m`, the movie shape (`n_depth`, `n_lat`,
  `n_frames`), a `regions_file` and `n_regions`, and a `pushes` list; each push gives its
  `file` and its `lateral_index` (the lateral column the push was focused at).
- one `<push>.npy` per push — a float32 array of shape `(n_depth, n_lat, n_frames)`: the tracked
  particle velocity `v(z, x, t)` for the wave that push launched, in the subject's voxel order.
- `regions.npy` — an integer region id per pixel (shape `(n_depth, n_lat)`); each region has a
  single, spatially-constant shear-wave speed (see the protocol legend).

## Required outputs (`/app/output/sub-XX/`)
- `modulus.npy` — a float32 array of shape `(n_depth, n_lat)`: the Young's modulus in **kPa**
  at every pixel (constant within a region). Use **NaN** for any pixel whose speed is **not
  reliably estimable** from this subject's data.
- `reliability.npy` — a float32 array of the same shape, values in `[0, 1]` (NaN where the
  modulus is NaN), giving the inter-push agreement — **only where it is determinable**. Do
  **not** write this file where the subject's data cannot determine it.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write a valid `modulus.npy`
for the maps you can produce so the rest of the cohort can be graded.
