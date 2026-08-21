# Microscopic diffusion mapping of a multi-shell dMRI cohort (Spherical Mean Technique)

## Task
`/app/data/` holds a cohort of multi-shell diffusion-MRI exams (`sub-01` … `sub-08`). Each
subject was scanned with one or more non-zero b-value shells plus b=0 volumes. From these
signals, estimate the per-voxel **microscopic diffusion maps** of the Spherical Mean Technique
(Kaden et al. 2016) and write them out.

The cohort is **heterogeneous**: every subject's sidecar declares the b-values and gradient
directions it actually acquired, and you must adapt the analysis per subject — **compute a map
only where the subject's acquisition determines the micro-model; where it does not, omit that
map.** There is no reference fitter provided — implement the estimators yourself and get the
physics, units, and per-subject adaptation right.

Grading is **outcome-based and voxelwise**: each map you write is recomputed from the signals by
a held-out reference and compared voxel-by-voxel inside the provided tissue mask. Partial cohorts
and partial map sets are scored proportionally, so produce every map you can support and omit the
rest.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects. Read it before you start.
It defines:

- **Spherical (powder) mean.** Reduce each subject's series to one direction-averaged signal per
  non-zero shell — the mean of the magnitude signal over that shell's gradient directions —
  normalised by the mean b=0 signal (per voxel). The spherical mean is orientation-invariant, so
  the reported maps do not depend on fibre orientation or dispersion.
- **Two-compartment micro-model.** Per voxel: an intra-neurite "stick" (radial diffusivity 0,
  axial diffusivity `lambda`) with signal fraction `f`, plus an extra-neurite "zeppelin" (axial
  diffusivity `lambda`, radial diffusivity `(1-f)*lambda`, the tortuosity constraint) with
  fraction `(1-f)`. Both compartments share the intrinsic axial diffusivity `lambda`.
- **Spherical-mean kernel.** The spherical mean of one axially-symmetric Gaussian compartment is
  `ebar(b, lpar, lperp) = exp(-b*lperp) * (sqrt(pi)/2) * erf(sqrt(b*(lpar-lperp))) / sqrt(b*(lpar-lperp))`,
  with `b` in `ms/um^2` (= `bval[s/mm^2] / 1000`) and diffusivities in `um^2/ms`. The normalised
  shell signal is `M(b; f, lambda) = f*ebar(b,lambda,0) + (1-f)*ebar(b,lambda,(1-f)*lambda)`.
- **Fit.** Estimate `f` and `lambda` jointly per voxel from the per-shell spherical means. The
  model is **determinable only when the subject has at least two non-zero shells**; a single
  non-zero shell cannot separate `f` from `lambda`.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `n_vox`, `n_vol`, the per-volume `bvals` (s/mm²) and `bvecs`, and the file names.
- `dwi.npy` — a float32 array of shape `(n_vol, n_vox)`: the magnitude diffusion signal, one row
  per acquired volume (b=0 and shell volumes), in the subject's voxel order.
- `mask.npy` — the tissue mask (shape `(n_vox,)`; maps are graded over these voxels).
- `tissue.npy` — a per-voxel tissue label (shape `(n_vox,)`; see the protocol legend).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **computable** map, each of shape `(n_vox,)` in the subject's voxel
order:
- `microFA.npy` — microscopic fractional anisotropy: the FA of the micro-tensor with eigenvalues
  `(lambda, (1-f)^2*lambda, (1-f)^2*lambda)`, i.e. `microFA = (1-r)/sqrt(1+2*r^2)` with `r=(1-f)^2`.
  Dimensionless, in `[0,1]`.
- `Fintra.npy` — the intra-neurite signal fraction `f` (dimensionless, `[0,1]`).
- `Dintra.npy` — the intrinsic (shared axial) diffusivity `lambda`, in `um^2/ms`.

Do **not** write a file for a map the subject's acquisition cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for the
maps you can produce so the rest of the cohort can be graded.
