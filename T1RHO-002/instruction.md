# Quantitative T1rho relaxometry of a heterogeneous spin-lock cohort

## Task
`/app/data/` holds a cohort of spin-lock (rotating-frame, T1rho) relaxometry exams
(`sub-01` … `sub-08`). Each subject was scanned with **one spin-lock series**: a stack of
magnitude images acquired at a set of **spin-lock times** (TSL, ms) at a single spin-lock
frequency. From these signals, estimate the per-voxel **rotating-frame relaxation maps** and
write them out.

The cohort is **heterogeneous**: every subject's sidecar declares the spin-lock times it
actually sampled, and the number of samples decides which model its data can support — so a
pipeline that assumes one fixed recipe will not fit them all. **Report a quantity only where
the subject's sampling determines it; where it does not, omit that map.** There is no reference
fitter provided — implement the estimators yourself and get the model, units, and per-subject
adaptation right.

Grading is **outcome-based and voxelwise**: each map you write is recomputed from the signals
by a held-out reference and compared voxel-by-voxel. Partial cohorts and partial map sets are
scored proportionally, so produce every map you can support and omit the rest.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the mono- and
**bi-exponential** spin-lock **signal models**, the **model-order rule** (how the number of
spin-lock times decides whether the bi-exponential model is determinable), the exact
**estimator definition** (least-squares fit of the applicable model; the component **ordering**
convention `T1rho_short ≤ T1rho_long` and the meaning of the **fraction**), the **unit** of each
quantity, the **grading regions**, and the **tissue legend**. Read it before you start.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `fsl_hz` (spin-lock frequency), `n_vox`, `tsl_ms` (the list of spin-lock
  times), and the `signal_file` / `tissue_file` / `mask_file` names.
- `signal.npy` — a float32 array of shape `(n_TSL, n_vox)`: the magnitude spin-lock signal,
  one row per spin-lock time, in the subject's voxel order.
- `tissue.npy` — per-voxel tissue label (shape `(n_vox,)`; see the protocol legend, GM = 1,
  WM = 2, CSF = 3).
- `mask.npy` — the brain mask (shape `(n_vox,)`).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **determinable** map, each of shape `(n_vox,)` in the subject's
voxel order:
- `T1rho.npy` — mono-exponential rotating-frame relaxation time (ms) — **only where the
  bi-exponential model is not determinable**.
- `T1rho_short.npy` — short (fast) component (ms) — **only where determinable**.
- `T1rho_long.npy` — long (slow) component (ms) — **only where determinable**.
- `fraction.npy` — short-component fraction (dimensionless) — **only where determinable**.

Do **not** write a file for a map the subject's sampling cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for
the maps you can produce so the rest of the cohort can be graded.
