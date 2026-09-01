# First-level fMRI GLM of a heterogeneous single-run cohort

## Task
`/app/data/` holds a cohort of first-level fMRI exams (`sub-01` … `sub-08`). Each subject has a
single BOLD run, an events table, realignment parameters, and a brain mask. Build the
first-level general linear model for each subject — design matrix, fit, and contrast maps — and
write the per-voxel results.

The cohort is **heterogeneous**: the repetition time, run length, event timing, and whether the
events table carries a parametric **modulation** all vary per subject, so read each subject's
sidecar and events table and adapt the design — one fixed recipe will not fit them all.
**Report a contrast only where the subject's design determines it; where it does not, omit it.**
There is no GLM library provided — implement the design build, prewhitening, and inference
yourself and get the conventions, units, and per-subject adaptation right.

Grading is **outcome-based and voxelwise**: each map you write is compared, voxel-by-voxel
inside the brain mask, to the held-out target produced by the **pinned** first-level GLM defined
below. Because every convention the graded quantities depend on is pinned exactly (the provided
HRF, the design/convolution, the modulation regressor, the drift, the motion-spike modelling,
and the AR(1) prewhitening with N−p degrees of freedom), the beta and t-statistic are **uniquely
determined by the data** — **any correct implementation of the pinned conventions recovers the
same values within tolerance** (an FFT or a direct convolution, an explicit whitening matrix or
the Prais–Winsten transform, any linear-algebra backend all agree). You are **not** required to
reproduce any particular reference implementation's code. Each (subject × quantity) is scored
independently, so produce every quantity you can support and omit the rest.

## Shared design + inference contract (`/app/data/protocol.json`, `/app/data/hrf.npy`)
`protocol.json` pins every convention the graded quantities depend on and MUST be followed
exactly:
- the **HRF** (`hrf.npy`, the canonical response sampled at `dt = 0.1 s`) — use it **as given**;
- the **design**: how event onsets/durations become the task regressor (unit boxcars on the
  0.1 s micro-grid, convolved with the HRF, sampled at the frame times `t_i = i·TR`);
- the **modulation** regressor and when it is defined (see the omit rule below);
- the **nuisance** basis (the 6 realignment parameters + a degree-2 polynomial drift);
- the **prewhitening** (one pooled AR(1) coefficient per run, applied by the exact
  Prais-Winsten transform);
- the **inference**: the GLS effect size `beta` and its t-statistic for a single-column
  contrast.

Read it before you start. The betas carry the HRF/design scale, so following these conventions
exactly is what makes your numbers comparable to the reference.

## Robustness / data-quality contract  (READ THIS)
The runs are realistic, not clean:

- **Gross motion-spike frames.** In a **majority of subjects a few individual frames are
  grossly corrupted by a transient head motion** — a framewise displacement far above the run's
  small baseline floor, accompanied by a large BOLD transient that the 6 realignment parameters
  do **not** capture. You must **detect these frames from the realignment parameters and model
  them out before the fit** — one unit-impulse (spike) regressor per corrupted frame, or
  equivalently by censoring those frames — or the task and modulation betas and t-statistics are
  biased on the affected runs. **Which** frames (and which subjects) are corrupted is **not
  disclosed**; detect them from the data. Any framewise-displacement threshold that separates the
  gross transients from the baseline floor selects the same frames, and a **minority of runs have
  no corrupted frame** and need no spike regressor.

The AR(1) temporal autocorrelation is handled by the pinned prewhitening and needs no special
treatment beyond it.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `tr_s`, `n_frames`, `n_vox`, and the file names below.
- `bold.npy` — the BOLD data, a float32 array of shape `(n_frames, n_vox)` in the subject's
  voxel order.
- `events.tsv` — columns `onset`, `duration`, `trial_type` (all events are the single condition
  `task`), and **optionally** a `modulation` column of per-event amplitudes.
- `motion.npy` — the 6 realignment parameters, shape `(n_frames, 6)`, columns
  `[tx, ty, tz]` in mm and `[rx, ry, rz]` in radians.
- `mask.npy` — the brain mask, shape `(n_vox,)`; quantities are graded over these voxels.

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **computable** quantity, each of shape `(n_vox,)` in the subject's
voxel order:
- `beta_task.npy` — the task-condition contrast effect size (always).
- `tstat_task.npy` — its t-statistic (always).
- `beta_mod.npy` — the parametric-modulation contrast effect size — **only when the events table
  has a `modulation` column**.
- `tstat_mod.npy` — its t-statistic — **only when the events table has a `modulation` column**.

Do **not** write a file for the modulation contrast of a subject whose events table has no
`modulation` column.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for
the quantities you can produce so the rest of the cohort can be graded.
