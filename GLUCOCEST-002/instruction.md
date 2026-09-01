# Dynamic glucoCEST: quantify glucose uptake from a heterogeneous DGE-CEST cohort

## Task
`/app/data/` holds a cohort of dynamic glucose-enhanced (DGE) CEST exams (`sub-01` … `sub-08`).
Each exam is a **time series of Z-spectra** acquired over a small voxel grid during and after a
glucose infusion. The glucose-hydroxyl CEST signal in the **+2 ppm band** rises after infusion;
from the series, estimate the per-voxel **dynamic glucose uptake** and write it out.

The cohort is **heterogeneous**: every subject's sidecar declares its acquisition (number of
dynamics, when the infusion starts, offsets, field), and you must adapt the analysis per subject —
**compute a quantity only where the subject's acquisition determines it; where it does not, omit
it.** There is no reconstruction library provided — implement the physics, units, and per-subject
adaptation yourself, and get the dynamic quantification right on the data as acquired.

Grading is **outcome-based and voxelwise against the true underlying physiology**: each map you
write is compared voxel-by-voxel, inside the brain mask, to the *true* dynamic-glucoCEST map that
generated the data (the reference computed on the noise-free, drift-free, motion-free signal).
**Any scientifically valid estimator is accepted** — parabola or spline-grid water referencing,
per-voxel or global drift correction, whichever interpolation and frame-rejection scheme you
prefer — because the dynamic enhancement is a temporal difference and every correct method
recovers the same values within tolerance. You are **not** required to reproduce any particular
reference implementation's output. Each `(subject, map)` panel is scored independently, so produce
every map you can support and omit the rest.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects. **Read it before you
start.** It pins: the **Z normalisation** (`zdyn.npy` already holds `Z = S_sat / S0`); the **B0
convention** (`b0.npy` gives the per-voxel static water offset; the water resonance is the
direct-saturation minimum and is not at 0 ppm — reference each spectrum to it); the **glucose-band
CEST signal** `L` (the trapezoidal integral of `1 − Z`
over the glucose band on the water-referenced axis, with interpolated band edges); the **dynamic
enhancement** `dL(t) = L(t) − L_baseline` relative to the pre-infusion baseline; and the exact
definitions and units of the two graded maps, **`auc`** (trapezoidal time-integral of `dL` over
the post-infusion dynamics) and **`rate`** (the initial uptake slope — OLS slope of `dL` over the
first few post-infusion dynamics), including the rule that fixes when `rate` is **determinable**.

## Robustness / data-quality contract  (READ THIS)
The Z-spectra are realistic, not clean. Three artifacts must be handled, or they masquerade as
glucose uptake:

- **Per-timepoint frequency drift.** On most subjects the scanner centre frequency **drifts over
  the dynamic series**, so the whole Z-spectrum slides along the offset axis with time (on top of
  the static per-voxel B0). You must **track this drift per timepoint** — locate the water
  resonance in *each* dynamic and reference the glucose band to it — not just apply the static
  `b0.npy` once. A minority of subjects have negligible drift. A pipeline that references only by
  the static field map reads the drift as spurious enhancement and fails those subjects. *Which*
  subjects drift is **not disclosed**.
- **Grossly motion-corrupted dynamic frames.** In a **minority of subjects, one or two individual
  post-infusion dynamic frames are grossly corrupted** (motion: the whole frame's band signal is a
  gross temporal outlier). **Detect and reject such frames robustly** (and repair by temporal
  interpolation) before integrating the AUC / fitting the rate. *Which* subjects and *which* frames
  are affected is **not disclosed** — find them from the data. Any scientifically valid robust
  scheme is acceptable.
- **Pre-infusion baseline trend.** On some subjects the pre-infusion band signal is **not flat** but
  drifts linearly. The dynamic-enhancement baseline `L_baseline` must be the **fitted pre-infusion
  TREND** (a line over the pre-infusion timepoints), not a single constant level, or a genuine
  baseline drift is read as enhancement.

Modest per-point measurement noise is present on every spectrum and needs no special handling
beyond the ordinary integrals/fits.

## Per subject (`/app/data/sub-XX/`)
- `zdyn.npy` — the normalised Z-spectra, a float32 array of shape `(n_time, n_offset, n_vox)`:
  one Z-spectrum per dynamic timepoint per voxel, in the subject's voxel order.
- `offsets.npy` — the acquired saturation offsets `Δω` in ppm, shape `(n_offset,)`, ascending.
- `times.npy` — the acquisition time of each dynamic in minutes, shape `(n_time,)`.
- `b0.npy` — the per-voxel **static** water-resonance offset in ppm (from a field map), shape
  `(n_vox,)`.
- `mask.npy` — the brain mask, shape `(n_vox,)` (maps are graded over these voxels).
- `sidecar.json` — `field_T`, `f0_mhz`, `n_vox`, `n_time`, `n_offset`, `infusion_index` (the index
  of the first post-infusion dynamic; timepoints before it are the pre-infusion baseline),
  `n_post_infusion`, `glucose_offset_ppm`, `glucose_band_ppm`, and the file names above.

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **determinable** map, each of shape `(n_vox,)` in the subject's voxel
order:
- `auc.npy` — the dynamic glucoCEST AUC (ppm·min).
- `rate.npy` — the initial glucose uptake rate (ppm/min) — **only where determinable**.

Do **not** write a file for a map the subject's acquisition cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for the
maps you can produce so the rest of the cohort can be graded.
