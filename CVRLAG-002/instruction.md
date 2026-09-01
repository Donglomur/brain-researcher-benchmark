# Lag-optimized cerebrovascular-reactivity (CVR) mapping of a heterogeneous BOLD-CO2 cohort

## Task
`/app/data/` holds a cohort of BOLD-fMRI CO2-reactivity exams (`sub-01` … `sub-08`). Each
subject has one BOLD run and a CO2 regressor. From these, estimate the per-voxel **hemodynamic
lag** and, where determinable, the per-voxel **CVR amplitude**, and write them out.

The cohort is **heterogeneous**: each subject's sidecar declares its TR, its regressor source,
and (for an externally measured PetCO2 trace) that trace's sampling interval, start offset and
units — and you must adapt the analysis per subject, because a pipeline that assumes one fixed
recipe will not fit them all. **Compute a map only where the subject's acquisition determines
it; where it does not, omit that map.** There is no reference pipeline provided — implement the
estimators yourself and get the timing, units, and per-subject adaptation right.

Grading is **outcome-based and voxelwise against the true underlying physiology**. Each map you
write is compared voxel-by-voxel, over the well-determined brain voxels, to the *true* physical
quantity that generated the signals (the planted hemodynamic lag; the planted reactivity). **Any
scientifically valid estimator is accepted** — any backend, spike detector, or per-voxel lag
search — because every correct method recovers the same lag/CVR within tolerance. You are **not**
required to reproduce any particular reference implementation's output. Partial cohorts and partial
map sets are scored proportionally, so produce every map you can support and omit the rest.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the conventions common to all subjects: the **BOLD percent-signal model**,
the **regressor convention** (how an external PetCO2 trace is resampled onto the BOLD frame grid
via its `petco2_dt_s`/`petco2_start_s`, versus the **data-driven** mask-mean regressor when no
external trace exists), the exact **lag definition** (the integer-frame shift `τ = k·TR`, of
either sign, maximizing the detrended Pearson correlation), the exact **CVR definition** (the
detrended slope at the optimal lag, in %BOLD per mmHg, determinable only for an mmHg regressor),
the **unit** of each quantity, and the **tissue legend**. Read it before you start.

## Robustness / data-quality contract  (READ THIS)
The signals are realistic, not clean:

- **Grossly corrupted frames.** In a **minority of subjects, a few individual BOLD frames are
  grossly motion-corrupted** (whole-frame signal spikes) and are physically inconsistent with the
  rest of the run. **You must detect and censor such corrupted frames robustly before the lag /
  CVR fit** (the framewise brain-mean signal exposes them). *Which* subjects and *which* frames are
  affected is **not disclosed** — you must find them from the data. Any scientifically valid robust
  scheme is acceptable (a robust MAD outlier test on the framewise mean, etc.); a fit that leaves
  the spikes in recovers the wrong lag/CVR on the affected subjects and fails those panels.

Modest measurement noise is present on every frame (and a spatial low-reactivity / high-noise
region is left below the grader's well-determined floor, so it is not graded); ordinary detrending
plus the lag fit handle the noise with no special treatment.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `n_time`, `n_vox`, `tr_ms`, `regressor_source`
  (`"external_petco2"` or `"data_driven"`), and the file names below. External subjects also give
  `petco2_file`, `petco2_units`, `petco2_dt_s`, and `petco2_start_s`.
- `bold.npy` — the BOLD run, a float32 array of shape `(n_time, n_vox)` in the subject's voxel
  order (one row per frame).
- `petco2.npy` — *(external subjects only)* the end-tidal CO2 trace, a float32 array `(n_samples,)`;
  sample `i` is at time `petco2_start_s + i·petco2_dt_s` seconds.
- `tissue.npy` — per-voxel tissue label `(n_vox,)` (see the protocol legend).
- `mask.npy` — the brain mask `(n_vox,)`; maps are graded over these voxels.

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **computable** map, each of shape `(n_vox,)` in the subject's voxel
order:
- `lag.npy` — hemodynamic lag (seconds).
- `CVR.npy` — cerebrovascular reactivity (%BOLD per mmHg) — **only where determinable**.

Do **not** write a file for a map the subject's acquisition cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for the
maps you can produce so the rest of the cohort can be graded.
