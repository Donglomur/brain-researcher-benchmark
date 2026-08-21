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

Grading is **outcome-based and voxelwise**: each map you write is recomputed from the BOLD (and
PetCO2) data by a held-out reference and compared voxel-by-voxel over the gradeable brain voxels.
Partial cohorts and partial map sets are scored proportionally, so produce every map you can
support and omit the rest.

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
