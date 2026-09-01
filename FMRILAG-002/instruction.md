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

Grading is **outcome-based and voxelwise**: the lag map you write is compared voxel-by-voxel
inside the brain mask to the *true underlying hemodynamic lag* — the held-out planted lag,
measured on the noise-free, spike-free signal relative to the same reference convention. **Any
scientifically valid estimator is accepted** (any spike detector, FFT or direct cross-
correlation, per-voxel peak search), because every correct method recovers the same lag within
tolerance. You are **not** required to reproduce any particular reference implementation's
output.

## Shared conventions and output contract (`/app/data/protocol.json`)
A single JSON with the conventions common to all subjects: the **signal model**, the **reference
convention** (the global whole-brain mean signal, or — where the global signal is dominated by a
non-neural artifact rather than the shared hemodynamic fluctuation — the gray-matter-restricted
mean; which case applies is not annotated and must be inferred from the data), the exact **lag
definition** (the integer-frame lagged Pearson cross-correlation, its peak refined to sub-TR
precision by parabolic interpolation, and the sign convention), the **significance convention**
(which voxels carry a lag and which must be omitted), the **unit** of the lag, and the **tissue
legend**. Read it before you start.

## Robustness / data-quality contract  (READ THIS)
The runs are realistic, not clean:

- **Gross motion-spike frames.** In a **majority of subjects a few frames are grossly corrupted
  by a motion transient** — a whole-brain intensity jump. **You must detect and censor these
  frames before the cross-correlation**, or the correlation is pulled toward zero lag and the lag
  estimate (and the significance decision) is biased. *Which* frames (and which subjects) are
  corrupted is **not disclosed**; detect them from the data (a robust framewise-outlier rule). A
  **minority of runs have no corrupted frame** and need no censoring.
- **Reference fork (restated).** On some subjects the whole-brain global signal is dominated by a
  non-neural artifact rather than the shared hemodynamic fluctuation; there you must restrict the
  reference to gray matter. Which subjects is **not disclosed** — infer it from the data (compare
  the global and gray-matter candidate references).
- **Non-vascular / low-SNR voxels.** A region of voxels does not follow the driver (its peak
  correlation is at the noise floor); those voxels carry no significant lag and must be **omitted**
  (NaN), not reported.

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
