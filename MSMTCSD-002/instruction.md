# Multi-shell multi-tissue spherical deconvolution of a heterogeneous dMRI cohort

## Task
`/app/data/` holds a cohort of multi-shell diffusion-MRI exams (`sub-01` … `sub-08`). Each
subject was scanned with one or more diffusion-weighted shells plus b0 volumes, and its own
gradient table. From these signals, estimate — per voxel — the **tissue signal fractions**
(white matter / grey matter / CSF) and the **white-matter fibre-orientation-distribution (FOD)
peaks**, using the **pinned** per-tissue response functions in the protocol.

The cohort is **heterogeneous**: every subject's sidecar declares the shells it actually
acquired, and you must adapt the analysis per subject — a pipeline that assumes one fixed
recipe will not fit them all. There is no reference implementation provided: build the
multi-tissue spherical-deconvolution estimator yourself and get the spherical-harmonic algebra,
the per-tissue convolution, and the tissue unmixing right.

Grading is **outcome-based and voxelwise**: each quantity you write is recomputed from the
signals by a held-out reference and compared voxel-by-voxel inside the brain mask.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects. Read it before you
start. It defines:
- the **signal model** — per voxel, a WM fibre-orientation distribution spherically convolved
  with the WM single-fibre response, plus isotropic GM and CSF compartments;
- the **pinned responses** — the WM single-fibre response (axial/radial diffusivities), the
  GM and CSF isotropic responses, and the WM spherical (powder) mean. Use **these**; do not
  estimate them;
- the **shell convention** — `b < 50` are b0; DW shells are grouped within ±6% relative b; the
  number of tissues that can be separated equals the number of **distinct b-values** (b0
  counts as one), capped at three;
- the **tissue-fraction definition** — the tissue **signal fractions** are the non-negative
  least-squares solution of the per-shell **spherical-mean** (direction-averaged) equations
  `sbar(b) = a_WM·Rbar_WM(b) + a_GM·R_GM(b) + a_CSF·R_CSF(b)` (with the b0 row `sbar(0)=1` and
  all responses `=1` at b=0), **normalised to sum to one** over the tissues present. With three
  or more distinct b-values solve for (WM, GM, CSF); with only two distinct b-values GM is not
  separable — solve for (WM, CSF) and **omit** the GM fraction;
- the **FOD / peak definition** — the WM FOD from Laplace-Beltrami-regularised spherical
  deconvolution with the pinned WM response, the usable `lmax` rule, and the amplitude /
  relative / separation / anisotropy thresholds that define a peak (and that near-isotropic
  voxels have **no** peak);
- the exact **output spec**.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `n_vox`, `n_meas`, the `shells` present (each `b` and its direction count),
  the number of b0 volumes, and the file names below.
- `dwi.npy` — the signal, a float32 array of shape `(n_meas, n_vox)`: one row per acquired
  volume (b0s and diffusion-weighted), in the subject's voxel order.
- `bvals.npy` — `(n_meas,)` b-values (s/mm²); `bvecs.npy` — `(n_meas, 3)` unit gradient
  directions (zero for b0 rows).
- `mask.npy` — the brain mask (`(n_vox,)`; quantities are graded over these voxels).

## Required outputs (`/app/output/sub-XX/`)
Write float32 `.npy` arrays per subject:
- `wm_frac.npy` — `(n_vox,)` WM signal fraction.
- `csf_frac.npy` — `(n_vox,)` CSF signal fraction.
- `gm_frac.npy` — `(n_vox,)` GM signal fraction — **only where the protocol determines it**;
  omit the file for subjects whose acquisition cannot separate GM.
- `peaks.npy` — `(n_vox, 3, 3)`: up to **3** WM-FOD peak unit vectors per voxel, ordered by
  descending amplitude, unused peak slots all-zero. A voxel with no reliable fibre peak has an
  all-zero block.

Do **not** write a file for a fraction the subject's acquisition cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid outputs for the
quantities and subjects you can produce so the rest of the cohort can be graded.
