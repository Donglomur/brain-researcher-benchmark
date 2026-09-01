# Resting-state cerebrovascular-reactivity (CVR) & hemodynamic-lag mapping

## Task
`/app/data/` holds a cohort of **resting-state** BOLD-fMRI exams (`sub-01` … `sub-08`). There is
no gas challenge and no task: the vasoactive drive is the subject's own **natural low-frequency
fluctuation of end-tidal CO2** (a slow, ~0.01–0.1 Hz systemic oscillation). From each resting
run, estimate the per-voxel **hemodynamic lag** and the per-voxel **reactivity amplitude**, and
write them out.

The cohort is **heterogeneous**: each subject's sidecar declares its TR, whether an external
PetCO2 trace was recorded (and that trace's sampling, start offset and units) or not, and you
must adapt the analysis per subject — a pipeline that assumes one fixed recipe will not fit them
all. **Compute a map only where the subject's acquisition determines it; where it does not, omit
that map.** There is no reference pipeline provided — implement the estimators yourself and get
the timing, units, and per-subject adaptation right.

## What is graded
Grading is **outcome-based and voxelwise against the true underlying physiology**. Each map you
write is compared voxel-by-voxel, over the gradeable brain voxels, to the *true* map that
generated the signals (the reference model run on the noise-free, artefact-free BOLD+PetCO2).
**Any scientifically valid estimator is accepted** — whichever sub-frame lag refinement,
regressor upsampling, linear algebra, or robust spike-censoring scheme you prefer — because
every correct method recovers the same physiology within tolerance. You are **not** required to
reproduce any particular reference implementation's output. Each (subject × map) is scored
independently and partial cohorts/map-sets are scored proportionally, so produce every map you
can support and omit the rest.

## Robustness / data-quality contract  (READ THIS)
The signals are realistic, not clean:

- **Gross motion-spike frames.** In a **majority of subjects, a few individual BOLD frames are
  grossly corrupted** (large motion-driven intensity spikes) and are physically inconsistent
  with the rest of the run. **You must detect and censor such corrupted frames robustly before
  the fit** — an uncensored spike distorts the temporal mean, the detrending, the lag search and
  the reactivity slope. *Which* subjects and *which* frames are affected is **not disclosed** —
  you must find them from the data. Any scientifically valid robust scheme is acceptable.
- **A low-SNR cluster.** Each subject also carries a spatial cluster of poorly-reactive,
  high-noise voxels; these fall below the grader's reliability floor and are **excluded from the
  graded voxel set** (you do not need to special-case them, but do write finite values there).
- **Continuous (sub-frame) lag.** Because the natural drive is slow and smooth, the true
  per-voxel delay is a *fraction of a TR* and of **either sign**; an integer-frame (`k·TR`) peak
  is too coarse and must be refined to sub-frame resolution.

Modest measurement noise is present throughout and needs no special handling beyond an ordinary
fit. The resting-state CVR / systemic-low-frequency-oscillation method is the standard one
(Liu et al. 2017, *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2016.11.054; Tong &
Frederick 2014, *NeuroImage*).

## Shared conventions and output contract (`/app/data/protocol.json`)
A single JSON with the conventions common to all subjects: the **percent-BOLD model**, the
**regressor convention** (how an external PetCO2 trace is converted to mmHg and resampled onto
the BOLD frame grid via its `petco2_units` / `petco2_dt_s` / `petco2_start_s`, versus the
**data-driven** mask-mean regressor when no external trace exists), the exact **lag definition**
(the *continuous, sub-frame* shift of either sign that maximises the detrended cross-correlation),
the exact **reactivity definitions** (`rCVR`, the gray-matter-normalised residual slope at the
optimal lag; and `CVR`, the absolute slope in %BOLD per mmHg, determinable only for an external
PetCO2 regressor), the **unit** of each quantity, and the **tissue legend**. Read it before you
start.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `n_time`, `n_vox`, `tr_ms`, `regressor_source` (`"external_petco2"` or
  `"data_driven"`), and the file names below. External subjects also give `petco2_file`,
  `petco2_units` (`"mmHg"` or `"kPa"`), `petco2_dt_s`, and `petco2_start_s`.
- `bold.npy` — the resting BOLD run, a float32 array of shape `(n_time, n_vox)` in the subject's
  voxel order (one row per frame).
- `petco2.npy` — *(external subjects only)* the end-tidal CO2 trace, a float32 array
  `(n_samples,)`; sample `i` is at time `petco2_start_s + i·petco2_dt_s` seconds.
- `tissue.npy` — per-voxel tissue label `(n_vox,)` (see the protocol legend; gray matter = 1).
- `mask.npy` — the brain mask `(n_vox,)`; maps are graded over the gradeable voxels within it.

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **computable** map, each of shape `(n_vox,)` in the subject's voxel
order:
- `lag.npy` — hemodynamic lag (seconds), the continuous cross-correlation-peak shift (either sign).
- `rCVR.npy` — relative cerebrovascular reactivity (dimensionless, gray-matter-normalised).
- `CVR.npy` — absolute cerebrovascular reactivity (%BOLD per mmHg) — **only where determinable**.

Do **not** write a file for a map the subject's acquisition cannot support. Still write a
full-length `(n_vox,)` map with finite values everywhere inside the brain mask for the maps you
do produce.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for the
maps you can produce so the rest of the cohort can be graded.
