# Hemodynamic-lag mapping of a resting-state BOLD cohort

## Task
`/app/data/` holds a cohort of resting-state BOLD-fMRI exams (`sub-01` … `sub-08`). Each subject
has one BOLD run. A shared systemic low-frequency hemodynamic fluctuation sweeps across the brain
and reaches each voxel at a slightly different time; from the BOLD run, estimate the per-voxel
**hemodynamic lag** relative to the subject's reference signal, and write it out.

The cohort is **heterogeneous**: TR differs between subjects, and the reference signal that best
represents the shared fluctuation is not the same construction for every subject — you must adapt
the analysis per subject, because a pipeline that assumes one fixed recipe will not fit them all.
There is no reference pipeline provided — implement the estimator yourself and get the timing,
sign, units, and per-subject adaptation right.

Grading is **outcome-based and voxelwise**: the lag map you write is recomputed from the BOLD
data by a held-out reference and compared voxel-by-voxel inside the brain mask.

## Shared conventions and output contract (`/app/data/protocol.json`)
A single JSON with the conventions common to all subjects: the **signal model**, the **reference
convention** (the global whole-brain mean signal, or — where the global signal is dominated by a
non-neural artifact rather than the shared hemodynamic fluctuation — the gray-matter-restricted
mean; which case applies is not annotated and must be inferred from the data), the exact **lag
definition** (the integer-frame lagged Pearson cross-correlation, its peak refined to sub-TR
precision by parabolic interpolation, and the sign convention), the **significance convention**
(which voxels carry a lag and which must be omitted), the **unit** of the lag, and the **tissue
legend**. Read it before you start.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `n_time`, `n_vox`, `tr_ms`, and the file names below.
- `bold.npy` — the BOLD run, a float32 array of shape `(n_time, n_vox)` in the subject's voxel
  order (one row per frame).
- `tissue.npy` — per-voxel tissue label `(n_vox,)` (see the protocol legend; gray matter = 1).
- `mask.npy` — the brain mask `(n_vox,)`; the lag is graded over these voxels.

## Required output (`/app/output/sub-XX/`)
Write `lag.npy`, a float32 array of shape `(n_vox,)` in the subject's voxel order:
- the per-voxel hemodynamic lag in **seconds** (of either sign) at voxels that carry a
  **significant** lag, and
- **NaN** at voxels that do not (they must be omitted, not reported).

## Failure handling
If a subject cannot be processed for an unexpected reason, still write a valid `lag.npy` for the
subjects you can produce so the rest of the cohort can be graded.
