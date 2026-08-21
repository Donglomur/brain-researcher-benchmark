# Restriction-spectrum imaging (RSI) of a heterogeneous multi-shell diffusion cohort

## Task
`/app/data/` holds a cohort of multi-shell diffusion-MRI exams (`sub-01` … `sub-08`). Each
subject was scanned with a set of diffusion-weighted volumes at one or more b-values. From these
signals, estimate the per-voxel **restriction-spectrum maps** and write them out.

The cohort is **heterogeneous**: every subject's sidecar declares the b-values it actually
acquired, and you must adapt the analysis per subject — a pipeline that assumes one fixed recipe
will not fit them all. **Compute a map only where the subject's acquisition determines it; where
it does not, omit that map.** There is no reference fitter provided — implement the estimators
yourself and get the model, units, and per-subject adaptation right.

Grading is **outcome-based and voxelwise**: each map you write is recomputed from the signals by
a held-out reference and compared voxel-by-voxel inside the brain mask. Partial cohorts and
partial map sets are scored per panel, so produce every map you can support and omit the rest.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the model and conventions common to all subjects: the definition of the
**spherical (powder) mean** signal per shell and its **b0 normalisation**, the **pinned
three-scale isotropic basis** (`scale_diffusivities` = the restricted / hindered / free
diffusivities) that the b0-normalised decay is fit to by **non-negative least squares** to give
the **normalised signal fractions**, the exact **ADC** definition, the **determinability** rule
(what an acquisition must sample for the three-scale spectrum to be separable), the **unit** of
each quantity, and the **tissue legend**. Read it before you start.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `n_vox`, `n_volumes`, `b0_threshold`, the list of `shells` (distinct b>0
  b-values) with `n_shells`, and the file names below.
- `dwi.npy` — a float32 array of shape `(n_volumes, n_vox)`: the magnitude diffusion signal, one
  row per acquired volume, in the subject's voxel order.
- `bvals.npy` — the b-value (s/mm²) of each volume (shape `(n_volumes,)`).
- `bvecs.npy` — the gradient direction of each volume (shape `(n_volumes, 3)`).
- `tissue.npy` — per-voxel tissue label (shape `(n_vox,)`; see the protocol legend, white
  matter = 2).
- `mask.npy` — the brain mask (shape `(n_vox,)`; maps are graded over these voxels).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **computable** map, each of shape `(n_vox,)` in the subject's voxel
order:
- `ADC.npy` — mono-exponential apparent diffusion coefficient (mm²/s).
- `f_restricted.npy` — restricted (cellular) signal fraction — **only where determinable**.
- `f_hindered.npy` — hindered (extracellular) signal fraction — **only where determinable**.
- `f_free.npy` — free-water signal fraction — **only where determinable**.

Do **not** write a file for a map the subject's acquisition cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for the
maps you can produce so the rest of the cohort can be graded.
