# Intravoxel incoherent motion (IVIM) fitting of a heterogeneous diffusion cohort

## Task
`/app/data/` holds a cohort of diffusion-weighted exams (`sub-01` … `sub-08`). Each subject was
scanned with a set of b-values, and you must fit the **intravoxel-incoherent-motion (IVIM)**
bi-exponential diffusion–perfusion model per voxel and write out the estimated parameter maps.

The cohort is **heterogeneous**: every subject's sidecar lists the b-values it actually acquired,
and the b-value scheme determines **which IVIM parameters are even estimable**. Read each
subject's scheme and adapt — a pipeline that assumes one fixed recipe will not fit them all.
**Compute a map only where the subject's b-values determine it; where they do not, omit that map.**
There is no reference fitter provided — implement the estimators yourself and get the physics,
units, and per-subject adaptation right.

Grading is **outcome-based and voxelwise against the true underlying physiology**: each map you
write is compared voxel-by-voxel, inside the brain mask, to the *true* IVIM parameter that
generated the signals. **Any scientifically valid estimator is accepted** — a full biexponential
non-linear least-squares fit, a segmented fit, whichever robust gross-volume rejection you
prefer — because every correct method recovers the same physiology within tolerance; you are
**not** required to reproduce any particular reference implementation. `D` is graded tightly, `f`
with a moderate band (the perfusion fraction has a genuine method spread), and `D*` only loosely
(pseudo-diffusion is intrinsically ill-conditioned — its file must be present, positive and have
a physically-plausible median; its *omission* where unsupported is graded strictly).

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the model and conventions common to all subjects: the IVIM **signal model**
`S(b) = S0·[(1−f)·exp(−b·D) + f·exp(−b·(D+D*))]`, the **high-b threshold** `B_HIGH` beyond which
the perfusion compartment has decayed, the exact definitions and **units** of **D** (tissue
diffusivity, the high-b mono-exponential slope), **f** (perfusion fraction, `1 − S_intercept/S(b=0)`,
bounded to `[0,1]`), and **D\*** (pseudo-diffusion, from the low-b perfusion residual), and the tissue
legend. Read it before you start.

## Robustness / data-quality contract  (READ THIS)
The signals are realistic, not clean:

- **Grossly corrupted volumes.** In a **majority of subjects, one high-b diffusion-weighted
  volume is grossly corrupted** (a motion / signal-dropout artifact: the whole volume scaled by
  a gross factor) and is physically inconsistent with the mono-exponential decay of the rest of
  that subject's high-b samples. **You must detect and reject such a corrupted volume robustly
  before the high-b `D` fit** (and the b=0 intercept that feeds `f`). *Which* subjects and
  *which* volume are affected is **not disclosed** — find them from the data. Any scientifically
  valid robust scheme is acceptable (robust regression, log-residual outlier rejection, etc.); a
  non-robust fit over all volumes recovers the wrong `D` (and wrong `f`) on the affected subjects
  and fails those panels.
- **Rician noise** (modest, per-subject) is present on every volume and needs no special
  handling beyond an ordinary fit.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `n_vox`, the `bvals` list (s/mm², one per acquired volume, in row order), and the
  data/`mask`/`tissue` file names.
- `dwi.npy` — a float32 array of shape `(n_b, n_vox)`: row `j` is the magnitude diffusion signal at
  `bvals[j]`, in the subject's voxel order.
- `tissue.npy` — per-voxel tissue label (shape `(n_vox,)`; see the protocol legend).
- `mask.npy` — the brain mask (shape `(n_vox,)`; maps are graded over these voxels).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **estimable** map, each of shape `(n_vox,)` in the subject's voxel order:
- `D.npy` — tissue diffusivity (mm²/s).
- `f.npy` — perfusion fraction (dimensionless, `[0,1]`) — **only where determinable**.
- `Dstar.npy` — pseudo-diffusion coefficient (mm²/s) — **only where determinable**.

Do **not** write a file for a map the subject's b-value scheme cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for the
maps you can produce so the rest of the cohort can be graded.
