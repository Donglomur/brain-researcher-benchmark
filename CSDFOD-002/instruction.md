# Fibre orientation distributions for a heterogeneous diffusion-MRI cohort

## Task
`/app/data/` holds a cohort of diffusion-MRI exams (`sub-01` … `sub-09`). Each subject was
scanned with one or more diffusion-weighted shells and its own gradient table. From these
signals, estimate the per-voxel **fibre orientation distribution (FOD)** by spherical
deconvolution (Tournier 2004/2007) and write out the extracted fibre peaks.

The cohort is **heterogeneous**: every subject's sidecar declares the b-values, gradient
directions, and volume layout it actually acquired, and you must adapt the analysis per
subject — a pipeline that assumes one fixed recipe (one response kernel, one spherical-harmonic
order, one shell) will not fit them all. There is no reference implementation provided:
build the estimator yourself and get the spherical-harmonic algebra, the per-subject single-fibre
response, and the deconvolution right.

Grading is **outcome-based and voxelwise**: the FOD peaks you write are compared against a
held-out reference over the brain-mask voxels.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the diffusion **signal
model** (spherical convolution of the FOD with a single-fibre response plus an isotropic part),
the **shell convention** (`b < 50` are b0; estimate the FOD on the **outermost / highest-b**
shell), the **lmax rule** (largest even order whose SH count fits the usable directions,
capped at 8), the **response convention** (the single-fibre response is estimated from that
subject's own high-anisotropy voxels — it is not provided), the **FOD / peak definition**
(the AFD-normalised amplitude `ghat`, the amplitude and separation thresholds that define a
peak, and that near-isotropic voxels have **no** peak), the **coordinate frame**, and the exact
**output spec**. Read it before you start.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `n_vox`, `n_meas`, the `shells` present (each `b` and its direction count),
  and the file names below.
- `dwi.npy` — the signal, a float32 array of shape `(n_meas, n_vox)`: one row per acquired
  volume (b0s and diffusion-weighted), in the subject's voxel order. Voxels span coherent
  white-matter fibre populations and non-fibrous tissue; there is no tissue-label map.
- `bvals.npy` — `(n_meas,)` b-values (s/mm²); `bvecs.npy` — `(n_meas, 3)` unit gradient
  directions (zero for b0 rows).
- `mask.npy` — the brain mask (`(n_vox,)`; peaks are graded over these voxels).

## Required outputs (`/app/output/sub-XX/`)
Write three float32 `.npy` arrays per subject:
- `peaks.npy` — shape `(n_vox, 3, 3)`: up to **3** fibre-peak unit vectors per voxel, ordered
  by descending amplitude, unused peak slots all-zero. A voxel with no reliable fibre peak has
  an all-zero block.
- `amps.npy` — shape `(n_vox, 3)`: the matching peak amplitudes (the AFD-normalised `ghat` at
  each peak), unused slots 0.
- `response.npy` — shape `(7,)`: the single-fibre response you estimated for that subject, as
  its attenuation `R(theta)` at `theta = [0, 15, 30, 45, 60, 75, 90]` degrees from the fibre,
  normalised so `R(90 deg) = 1`.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid outputs for the
subjects you can process so the rest of the cohort can be graded.
