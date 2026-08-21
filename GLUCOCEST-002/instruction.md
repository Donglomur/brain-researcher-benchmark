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

Grading is **outcome-based and voxelwise**: each map you write is recomputed from the Z-spectra by
a held-out reference and compared voxel-by-voxel inside the brain mask. Each `(subject, map)` panel
is scored independently, so produce every map you can support and omit the rest.

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
