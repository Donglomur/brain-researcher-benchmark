# Composite hindered-and-restricted (CHARMED) diffusion of a heterogeneous dMRI cohort

## Task
`/app/data/` holds a cohort of multi-shell diffusion-MRI exams (`sub-01` … `sub-08`). Each
subject was scanned with a set of diffusion-weighted volumes at one or more b-value shells.
From these signals, estimate the per-voxel **composite hindered-and-restricted diffusion
parameters** and write them out.

The cohort is **heterogeneous**: every subject's sidecar declares the acquisition it actually
has (the b-value and gradient direction of each volume, and the diffusion pulse timing), and you
must adapt the analysis per subject — a pipeline that assumes one fixed recipe will not fit them
all. **Compute a quantity only where the subject's acquisition determines it; where it does not,
omit that map.** There is no reference fitter provided — implement the estimators yourself and
get the physics, units, and per-subject adaptation right.

Grading is **outcome-based and voxelwise against the true underlying physiology**. Each map you
write is compared voxel-by-voxel, inside the graded region, to the *true* physical quantity that
generated the signals (the planted restricted fraction and hindered mean diffusivity; the
identifiable lowest-shell DTI mean diffusivity). **Any scientifically valid estimator is accepted**
— a full or reduced nonlinear CHARMED fit, any optimiser, whichever robust volume-rejection scheme
you prefer — because every correct method recovers the same physics within tolerance. You are
**not** required to reproduce any particular reference implementation's output. Partial cohorts and
partial map sets are scored proportionally, so produce every map you can support and omit the rest.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the two-compartment
**signal model** (a hindered axially-symmetric tensor plus a restricted intra-axonal cylinder),
the **pinned constants** (the restricted cylinder radius `R` and intrinsic diffusivity `D_r`, and
`gamma`), the exact **Van Gelderen** expression for the restricted perpendicular signal, the
finite-pulse relation used to **derive the gradient strength** `G` per shell from `(b, delta,
Delta)`, and the exact definitions and **units** of each graded quantity:

- **`MD`** — the DTI mean diffusivity (µm²/ms) of the lowest shell (ordinary log-linear tensor
  fit to `b=0` + the lowest diffusion-weighted shell). Always determinable.
- **`f_restricted`** — the restricted (intra-axonal) signal fraction in `[0,1]` from the
  two-compartment CHARMED fit. Determinable only where the acquisition can separate the restricted
  compartment from the hindered one.
- **`MD_hindered`** — the hindered-compartment mean diffusivity (µm²/ms), `(Dpar_h + 2·Dperp_h)/3`,
  from the same fit. Same determinability as `f_restricted`.

Read it before you start.

## Robustness / data-quality contract  (READ THIS)
The signals are realistic, not clean:

- **Grossly corrupted whole DWI volumes.** In a **majority of subjects, several individual
  diffusion-weighted volumes are grossly corrupted** (e.g. bulk-motion signal dropout: a whole
  volume scaled far below the signal expected for its b-value and direction) and are physically
  inconsistent with the rest of that subject's acquisition. **You must detect and reject such
  corrupted volumes robustly before fitting** the DTI tensor and the CHARMED model. *Which*
  subjects and *which* volumes are affected is **not disclosed** — you must find them from the
  data. Any scientifically valid robust scheme is acceptable (a per-shell robust outlier test
  against a per-voxel angular baseline, robust regression, etc.); a fit over all volumes recovers a
  biased MD / hindered MD on the affected subjects and fails those panels.

Modest Rician noise is present on every volume and does **not** need special handling beyond an
ordinary fit.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `n_vox`, `n_meas`, the per-volume `bvals` (s/mm²) and unit `bvecs`, the pulse
  timing `delta_ms` and `Delta_ms`, and the file names below.
- `dwi.npy` — a float32 array of shape `(n_meas, n_vox)`: the diffusion signal (normalised so the
  `b=0` level is ≈ 1), one row per volume, in the subject's voxel order.
- `mask.npy` — the brain mask (shape `(n_vox,)`; maps are graded over these voxels).
- `tissue.npy` — per-voxel tissue label (shape `(n_vox,)`; see the protocol legend, white
  matter = 2, grey matter = 1, CSF = 3).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **determinable** map, each of shape `(n_vox,)` in the subject's voxel
order:
- `MD.npy` — DTI mean diffusivity (µm²/ms).
- `f_restricted.npy` — restricted signal fraction (dimensionless) — **only where determinable**.
- `MD_hindered.npy` — hindered mean diffusivity (µm²/ms) — **only where determinable**.

Do **not** write a file for a map the subject's acquisition cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for the
maps you can produce so the rest of the cohort can be graded.
