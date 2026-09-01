# Saturation-recovery T1 mapping of a heterogeneous SASHA-style cohort

## Task
`/app/data/` holds a cohort of saturation-recovery T1-mapping exams (`sub-01` … `sub-08`).
Each subject was scanned with a saturation-preparation pulse followed by an image at each of
several **saturation-recovery times** `TS`, with full longitudinal recovery between prep
repetitions. From each recovery series, estimate the per-voxel **T1** (and, where the
acquisition supports it, the residual ratio) and write the maps out.

The cohort is **heterogeneous**: every subject's sidecar declares its saturation scheme and its
`TS` schedule, and you must adapt the analysis per subject — a pipeline that assumes one fixed
recipe will not fit them all. **Estimate a map only where the subject's acquisition determines
it; where it does not, omit that map.** There is no reference fitter provided — implement the
estimator yourself and get the model, units, and per-subject adaptation right.

## What is graded
Grading is **outcome-based and voxelwise against the true underlying physiology**. Each map you
write is compared voxel-by-voxel, inside the brain mask, to the *true* quantitative map that
generated the signals (the model run on the noise-free, artefact-free recovery series). **Any
scientifically valid least-squares fit is accepted** — whichever nonlinear solver,
initialisation, or robust frame-rejection scheme you use — because saturation recovery carries no
inversion-efficiency / Look–Locker ambiguity and every correct fit recovers the same T1 and B/A
within tolerance. You are **not** required to reproduce any particular reference implementation's
output. Each (subject × map) panel is scored independently and partial cohorts/map-sets are
scored proportionally, so produce every map you can support and omit the rest.

## Robustness / data-quality contract  (READ THIS)
The recovery series are realistic, not clean:

- **Gross motion-corrupted frames.** In a **majority of subjects, one or two whole recovery
  frames are grossly corrupted** (scaled by a large motion factor) and are physically
  inconsistent with the saturation-recovery curve of the rest of the series. **You must detect
  and reject such corrupted frames robustly before the fit** — an uncorrected frame biases T1
  (and B/A). *Which* subjects and *which* frames are affected is **not disclosed** — you must
  find them from the data (they are gross outliers of the per-frame fit residual, far above the
  ~1–2 % noise floor). Any scientifically valid robust scheme is acceptable.

Modest Rician noise is present on every frame and needs no special handling beyond an ordinary
fit. Select the recovery model from the sidecar's `sat_scheme` (2-parameter for `train`,
3-parameter for `single`) and apply the determinability rule (minimum distinct `TS`) — a wrong
model or a wrongly-emitted/omitted map fails the affected panels.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the saturation-recovery
**signal model** `S(TS) = A·(1 − f·exp(−TS/T1))`, the rule that selects the **2-parameter**
(fixed-saturation, `f = 1`) versus **3-parameter** (free residual `f`) recovery model from the
sidecar's `sat_scheme`, the exact definitions and **units** of **T1** (ms) and **Bratio** =
`B/A` = `f` (dimensionless), the **determinability** rule (minimum distinct `TS` per model), and
the output spec. Read it before you start.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `field_T`, `f0_mhz`, `n_vox`, `n_ts`, `sat_scheme` (`"train"` or
  `"single"`), `tsat_ms` (the saturation-recovery times, ms), and the `series_file`,
  `tissue_file`, `mask_file` names.
- `series.npy` — a float32 array of shape `(n_ts, n_vox)`: the magnitude saturation-recovery
  signal, one row per `TS`, in the subject's voxel order.
- `tissue.npy` — per-voxel tissue label (shape `(n_vox,)`; see the protocol legend).
- `mask.npy` — the brain mask (shape `(n_vox,)`; maps are graded over these voxels).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **determinable** map, each of shape `(n_vox,)` in the subject's
voxel order:
- `T1.npy` — longitudinal recovery time constant (ms).
- `Bratio.npy` — the residual ratio `B/A` (dimensionless) — **only where determinable**.

Do **not** write a file for a map the subject's acquisition cannot determine.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for
the maps you can produce so the rest of the cohort can be graded.
