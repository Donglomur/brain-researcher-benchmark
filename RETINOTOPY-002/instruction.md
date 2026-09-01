# Population receptive-field (pRF) mapping of a heterogeneous retinotopy cohort

## Task
`/app/data/` holds a cohort of visual-fMRI retinotopic-mapping exams (`sub-01` … `sub-08`).
Each subject viewed moving-bar stimuli that swept the visual field while their BOLD response was
recorded. For every subject, fit a **2D-Gaussian population receptive field (pRF)** to each
voxel's time course and write out the per-voxel **eccentricity**, **polar angle**, and
**pRF size**.

The cohort is **heterogeneous**: every subject's sidecar declares its own acquisition (the TR,
the visual-field pixel→degree mapping, the sampled HRF, the number of bar-sweep directions, and
whether the response is compressive), and you must adapt the analysis per subject — a pipeline
that assumes one fixed recipe will not fit them all. There is no reference fitter provided —
implement the pRF model yourself and get the model, units, and per-subject adaptation right.

## What is graded
Grading is **outcome-based and voxelwise against the true pRF physiology**. Each map you write
is compared voxel-by-voxel, over the reliably-driven voxels, to the *true* pRF parameters that
generated the signals (eccentricity `= √(x0²+y0²)`, polar angle `= atan2(y0,x0)`, size `= σ`).
**Any scientifically valid pRF fitter is accepted** — whichever spike censoring, grid, optimiser,
or parameterisation you use — because the fit is well-posed and every correct method recovers the
same pRF within tolerance. You are **not** required to reproduce any particular reference
implementation's output. Each `(subject, map)` panel is graded independently.

## Robustness / data-quality contract  (READ THIS)
The signals are realistic, not clean:

- **Gross motion-spike timepoints.** In a **majority of subjects, a few individual timepoints
  are grossly corrupted** by large transients across all voxels (motion). **You must detect and
  censor these timepoints before fitting** — an uncensored spike collapses the variance-explained
  and corrupts the pRF estimate (and wrongly pushes reliably-driven voxels below the
  determinability threshold). *Which* subjects and *which* timepoints are affected is **not
  disclosed** — you must find them from the data. Any scientifically valid robust scheme is
  acceptable.
- **Use each subject's own HRF.** `hrf.npy` is the subject's sampled haemodynamic response; its
  peak timing varies across the cohort (canonical for some, shifted for most). Convolving with a
  hard-coded canonical HRF biases the fit on the shifted-HRF subjects.
- **Apply the declared model.** Where the sidecar declares a compressive (CSS) response, apply
  the compressive exponent and report the **raw** Gaussian σ (not σ/√n).
- **Determinability.** Only a minority of voxels carry a reliable pRF; report a voxel only where
  its variance-explained clears the announced R2 ≥ 0.30 rule, and write NaN elsewhere.

The pRF model is the standard one (Dumoulin & Wandell 2008, *NeuroImage*,
https://doi.org/10.1016/j.neuroimage.2007.09.034; Kay et al. 2013, *J. Neurophysiol.*,
compressive spatial summation). Modest measurement noise is present and needs no special
handling beyond an ordinary fit.

## Shared model and output contract (`/app/data/protocol.json`)
A single JSON with the model and conventions common to all subjects: the **pRF signal model**
(unit-height 2D-Gaussian × stimulus overlap → optional compressive drive → HRF convolution →
free gain and baseline per voxel), the **coordinate convention** (how aperture pixels map to
visual-field degrees), the **HRF convention**, the exact **definitions and units** of the three
output maps, and the **determinability rule** that decides where a pRF is reliably estimated.
Read it before you start.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `tr_s`, `n_t`, `n_vox`, `grid`, `deg_per_pixel`, `stim_max_ecc_deg`,
  `n_bar_directions`, `prf_model` (`"linear"` or `"compressive"`), `css_exponent` (the
  compressive exponent *n*, or `null`), and the file names below.
- `bold.npy` — the measured BOLD run, a float32 array of shape `(n_t, n_vox)` (one column per
  voxel, in the subject's voxel order).
- `apertures.npy` — the binary moving-bar stimulus, a uint8 array of shape `(n_t, grid, grid)`
  (1 where the bar covered a visual-field pixel at that timepoint).
- `hrf.npy` — the subject's haemodynamic response, already sampled at the subject's TR.

## Required outputs (`/app/output/sub-XX/`)
Write three float32 `.npy` files, each of shape `(n_vox,)` in the subject's voxel order:
- `eccentricity.npy` — pRF-centre eccentricity (deg).
- `polar_angle.npy` — pRF-centre polar angle (rad), as defined in the protocol.
- `prf_size.npy` — pRF size, the Gaussian standard deviation σ (deg).

Report a value only where the pRF is **determinable** (see the protocol's determinability rule);
set every **omitted** voxel to `NaN`. `polar_angle` is additionally `NaN` at the fovea, per the
protocol. Maps are graded over the determinable voxels.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for the
subjects you can produce so the rest of the cohort can be graded.
