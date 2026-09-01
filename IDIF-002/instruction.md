# Image-derived input function and kinetic outcome for a dynamic-PET cohort

## Task
`/app/data/` holds a cohort of dynamic-PET exams (`sub-01` … `sub-08`). Each subject is
described by time-activity curves (TACs): a set of carotid-artery ROI candidate voxels, a
perivascular tissue TAC, and a set of target-region TACs, all framed on the subject's own
schedule. From these, **extract the arterial input function (IDIF)** and compute the **per-region
kinetic outcome**, then write it out.

The cohort is **heterogeneous**: every subject's sidecar declares the tracer class, frame
schedule, tissue-spillover fraction, reference region, and whether arterial blood samples were
drawn, and you must adapt the analysis per subject — a pipeline that assumes one fixed recipe
will not fit them all. Every subject yields a scale-free **reference-region ratio** map; a
subject with arterial blood samples additionally yields an **absolute** map. **The absolute map
is determinable only when blood was sampled; where it is not, omit it.** There is no reference
tool provided — implement the estimators yourself and get the physics, units, and per-subject
adaptation right.

Grading is **outcome-based and per-region against the true underlying kinetics**: each map you
write is compared region-by-region to the *true* graphical macro-parameter that generated the
data (the reference IDIF + graphical analysis run on the clean, artifact-free TACs). **Any
scientifically valid estimator is accepted** — a different carotid voxel selection, a different
corrupted-frame detector, a different OLS backend, framewise or trapezoidal integration —
because every correct method recovers the same macro-parameter within tolerance. You are **not**
required to reproduce any particular reference implementation's output. Partial cohorts and
partial outputs are scored proportionally, so produce every map you can support and omit the one
you cannot.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the **IDIF model**
(partial-volume recovery + tissue spillover), the **recovery calibration** to arterial blood
samples, the exact **kinetic-outcome definitions** (Logan `VT` for reversible tracers, Patlak
`Ki` for irreversible), the **unit** of each quantity, and the **output fork**. Read it before
you start.

## Robustness / data-quality contract  (READ THIS)
The carotid ROI and the TACs are realistic, not clean. Handle these per subject:

- **Contaminated carotid voxels.** The carotid candidate voxels include **partial-volume /
  tissue-contaminated voxels** (an attenuated bolus peak with heavy tissue spillover) that must
  be **excluded** before you average the blood voxels into `A(t)`. Averaging them in biases the
  input function (and hence the recovery calibration and the absolute VT/Ki). *Which* voxels are
  contaminated is **not disclosed** — identify them from the data (their shape differs from a
  true blood voxel).
- **Grossly motion-corrupted frames.** In a **majority of subjects, one or two individual
  carotid frames on the bolus tail are grossly corrupted** (a motion/dead-frame drop, or a
  spike) and are inconsistent with the smooth input-function shape. **You must detect and reject
  such frames robustly before integrating the input function.** A tail-frame corruption barely
  moves a Logan (reversible) cumulative-integral slope but grossly biases a Patlak (irreversible)
  slope, so a pipeline that skips frame rejection is punished on the irreversible subjects'
  absolute Ki **and** their scale-free Krel. *Which* subjects and *which* frames are affected is
  **not disclosed**.
- **Tracer-class model fork.** Use the graphical model fixed by the subject's `tracer_class` —
  **Logan** for `reversible`, **Patlak** for `irreversible`. The wrong graphical model biases
  both outputs.

Modest count noise is present on every TAC and needs no special handling beyond the ordinary
averaging / graphical fit.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `tracer_class` (`reversible` / `irreversible`), `frame_start_s` and
  `frame_end_s` (frame boundaries), `n_frames`, `n_regions`, `reference_region_index`,
  `t_star_min` (the graphical-fit start time), `spillover_fraction`, `recovery_nominal`, the
  three array file names, and — **only when arterial blood was sampled** — `blood_samples`
  (a list of `{t_min, value}` plasma activities at frame mid-times).
- `carotid_tacs.npy` — float32 `(n_cvox, n_frames)`: the candidate carotid ROI voxel TACs.
- `tissue_tac.npy` — float32 `(n_frames,)`: the perivascular tissue TAC (the spillover source).
- `region_tacs.npy` — float32 `(n_regions, n_frames)`: the target-region TACs.

## Graded quantity (definition + convention anchors)
Form the carotid ROI blood TAC `A(t)` from `carotid_tacs.npy`, then:
- **Spillover correction:** `U(t) = A(t) − SP·Ctis(t)` with `SP = spillover_fraction` and
  `Ctis` the perivascular tissue TAC; the IDIF is `Cp(t) = U(t)/RC`.
- **Recovery `RC`:** when `blood_samples` are present, `RC = Σ_i U(t_i)·Cb_i / Σ_i Cb_i²`
  (the closed-form least-squares match of `U = RC·Cp` to the samples at their frames); without
  blood samples the recovery is not determinable and **absolute quantitation is not possible**.
- **Kinetic outcome** for each region, over the frames with **mid-time ≥ `t_star_min`** (times in
  **minutes**; cumulative integrals are **trapezoidal over frame mid-times** with the curve `= 0`
  at `t = 0`; the plot slope is **ordinary least squares of Y on X**):
  - reversible → **Logan `VT`** (mL/mL): `Y = ∫₀ᵗ Ctis / Ctis(t)`, `X = ∫₀ᵗ Cp / Ctis(t)`.
  - irreversible → **Patlak `Ki`** (mL/min/mL): `Y = Ctis(t)/Cp(t)`, `X = ∫₀ᵗ Cp / Cp(t)`.
- **Ratio** divides each region's per-region value by the `reference_region_index` region's value.

## Required outputs (`/app/output/sub-XX/`)
Write, per subject, up to **two** float32 `.npy` vectors of shape `(n_regions,)`:
- `ratio.npy` — **always**: the scale-free reference-region ratio. Reversible → `DVR = VT_j / VT_ref`;
  irreversible → `Krel = Ki_j / Ki_ref`. (The recovery scale cancels, so this needs no blood sample.)
- `kinetic.npy` — **only when arterial blood samples are present**: the absolute macro-parameter.
  Reversible → `VT`; irreversible → `Ki` (from the blood-calibrated recovery coefficient).

The physical quantity in each file is fixed by the subject's `tracer_class` (Logan for reversible,
Patlak for irreversible). Do **not** write `kinetic.npy` for a subject with no blood samples — its
recovery scale is undetermined and the absolute map is not determinable.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid output for the
subjects you can, so the rest of the cohort can be graded.
