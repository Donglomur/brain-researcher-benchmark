# Confound denoising of a heterogeneous resting-state fMRI cohort

## Task
`/app/data/` holds a cohort of resting-state fMRI exams (`sub-01` … `sub-08`). Each subject has
a BOLD run, its realignment (motion) parameters, an anatomical tissue segmentation, and — for
some subjects — a simultaneous physiological phase recording. Build each subject's **nuisance
confound design**, regress it out of every voxel's time series, and write the **cleaned
residual**; for subjects with a physiological recording, also write the per-voxel BOLD variance
that the physiological regressors remove.

The cohort is **heterogeneous**: every subject's sidecar declares its TR, run length, and
whether a physiological recording is present, and you must adapt the confound model per subject —
a pipeline that assumes one fixed recipe will not fit them all. **Produce an output only where
the acquisition determines it; where it does not, omit that output.**

Grading is **outcome-based and voxelwise**: each output you write is recomputed from the saved
arrays by a held-out reference and compared voxel-by-voxel inside the brain mask. There is no
reference implementation provided — build the design and the regression yourself and get the
conventions, the per-subject adaptation, and the numerics right.

## Shared model and output contract (`/app/data/protocol.json`)
A single JSON with the confound model and conventions common to all subjects: the **Friston-24
motion** expansion, the **discrete-cosine high-pass** set (with its TR- and run-length-dependent
size `K = floor(2·n_vol·TR/128)`), the **anatomical CompCor** definition (top-5 temporal
components of the z-scored WM/CSF time series), the **RETROICOR** block for subjects with a
physiological recording (Fourier orders 3/3 of the cardiac and respiratory phases sampled at the
frame times), the **regression** (ordinary least squares; the cleaned time series is the
residual, i.e. the projection of the BOLD onto the orthogonal complement of the confound column
space — independent of the component/cosine basis), and the exact definitions and units of the
two graded outputs. Read it before you start.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `tr_s`, `n_vol`, `n_vox`, `physio` (bool), and, when `physio` is true,
  `physio_fs` plus the cardiac/respiratory phase file names.
- `bold.npy` — the BOLD run, a float32 array of shape `(n_vol, n_vox)` (one row per volume, in
  the subject's voxel order).
- `motion.npy` — the realignment parameters, float32 `(n_vol, 6)`: 3 translations (mm) then 3
  rotations (rad).
- `tissue.npy` — per-voxel tissue label, `(n_vox,)` (see the protocol legend: GM=1, WM=2, CSF=3).
- `mask.npy` — the brain mask, `(n_vox,)`; outputs are graded over these voxels.
- `cardiac_phase.npy` / `resp_phase.npy` — present only when `physio` is true; each a 1-D
  float32 array of instantaneous phase (radians) sampled at `physio_fs` Hz.

## Required outputs (`/app/output/sub-XX/`)
- `clean.npy` — float32 `(n_vol, n_vox)`, the cleaned residual time series (same shape as
  `bold.npy`), in the subject's voxel order. Always required.
- `physio_var.npy` — float32 `(n_vox,)`, the per-voxel BOLD variance removed specifically by the
  RETROICOR block (defined in the protocol) — **only where determinable**. Do **not** write this
  file for a subject with no physiological recording.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for
the outputs you can produce so the rest of the cohort can be graded.
