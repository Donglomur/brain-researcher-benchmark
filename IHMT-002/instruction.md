# Quantitative inhomogeneous magnetization transfer (ihMT) of a heterogeneous cohort

## Task
`/app/data/` holds a cohort of inhomogeneous-magnetization-transfer (ihMT) brain exams
(`sub-01` … `sub-08`). Each subject was scanned with a set of magnetization-prepared
acquisitions — an unsaturated reference plus one or more single- and/or dual-frequency
saturated acquisitions. From these signals, estimate the per-voxel **quantitative ihMT maps**
and write them out.

The cohort is **heterogeneous**: every subject's sidecar declares the acquisitions it actually
collected (role, saturation offset, dual interpulse spacing, number of repeated dynamics), and
you must adapt the analysis per subject — a pipeline that assumes one fixed saturation scheme
will not fit them all. **Compute a map only where the subject's acquisition determines it;
where it does not, omit that map.** There is no reference fitter provided — implement the
estimators yourself and get the physics, units, and per-subject adaptation right.

Grading is **outcome-based and voxelwise**: each map you write is recomputed from the signals
by a held-out reference and compared voxel-by-voxel inside the brain mask.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the ihMT **signal
model**, the **acquisition roles** (reference / single / dual), the exact definitions of
**MTR**, **ihMTR** (the difference-of-differences ratio at the reference dual condition) and
**T1D** (the dipolar relaxation time from the single-exponential decay of ihMTR with
interpulse spacing), the **B1+ convention**, the **unit** of each quantity, and the **tissue
legend**. Read it before you start.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `field_T`, `f0_mhz`, `n_vox`, `single_offset_hz`, and an `acquisitions`
  list; each acquisition gives its `role` (`reference` | `single` | `dual`), `offset_hz` (the
  saturation offset; sign gives the sideband), `dt_ms` (the dual interpulse spacing, dual only),
  `n_dyn`, and the `file` holding its signal.
- one `<file>.npy` per acquisition — a float32 array of shape `(n_dyn, n_vox)`: `n_dyn`
  repeated dynamics of that measurement, one column per voxel, in the subject's voxel order.
- `b1.npy` — the per-voxel transmit factor B1 (shape `(n_vox,)`, 1.0 = nominal).
- `tissue.npy` — per-voxel tissue label (shape `(n_vox,)`; see the protocol legend, white
  matter = 2).
- `mask.npy` — the brain mask (shape `(n_vox,)`; maps are graded over these voxels).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **computable** map, each of shape `(n_vox,)` in the subject's
voxel order:
- `MTR.npy` — single-frequency magnetization-transfer ratio (dimensionless fraction).
- `ihMTR.npy` — inhomogeneous-MT ratio (dimensionless fraction) — **only where determinable**.
- `T1D.npy` — dipolar relaxation time (ms) — **only where determinable**.

Do **not** write a file for a map the subject's acquisition cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for
the maps you can produce so the rest of the cohort can be graded.
