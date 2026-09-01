# Background-suppressed pCASL cerebral blood flow of a heterogeneous cohort

## Task
`/app/data/` holds a cohort of background-suppressed, single-PLD pseudo-continuous
arterial-spin-labeling (pCASL) perfusion exams (`sub-01` … `sub-08`). Each subject was scanned
with background-suppressed label/control repetitions. From these signals, estimate the per-voxel
**cerebral blood flow (CBF)** in **mL/100g/min** and the per-voxel **relative CBF (rCBF)**, and
write them out.

The cohort is **heterogeneous**: every subject's sidecar declares its label duration, PLD,
labeling efficiency, blood T1, the number of background-suppression pulses, and how (if at all)
the equilibrium magnetization M0 can be obtained, and you must adapt the analysis per subject — a
pipeline that assumes one fixed recipe will not fit them all. **Compute a quantity only where the
subject's acquisition determines it; where it does not, omit that map.** There is no reference
quantifier provided — implement the estimators yourself and get the physics, units, and
per-subject adaptation right.

Grading is **outcome-based and voxelwise against the true underlying physiology**. Each map you
write is compared voxel-by-voxel, inside the grey- and white-matter masks, to the *true*
quantity that generated the signals. **Any scientifically valid estimator is accepted** —
whatever robust repetition rejection or saturation-recovery fit backend you prefer — because
every correct method recovers the same physiology within tolerance. You are **not** required to
reproduce any particular reference implementation's output. Subjects and maps are scored
independently, so produce every map you can support and omit the rest.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the single-compartment
(blood-T1) **pCASL kinetic model** relating the repetition-averaged perfusion difference
`dM = <control> − <label>` to CBF in the fully-arrived regime; the **background-suppression
correction** (`dM_true = dM_meas / eps**n_bgs`, applied before quantification); the exact
**CBF equation** and the **rCBF** definition; the **M0 calibration paths** keyed by the
sidecar's `m0_source`; the shared physical constants (partition coefficient λ, per-pulse
inversion efficiency `eps`, pinned tissue T1); and the **tissue legend**. Read it before you
start.

## Robustness / data-quality contract  (READ THIS)
The signals are realistic, not clean:

- **Grossly corrupted repetitions.** In a **majority of subjects, one control/label repetition
  (and, for an `m0_scan` subject, one M0 repetition) is grossly corrupted** (e.g. by motion — the
  whole plane scaled by a large factor) and is physically inconsistent with the rest of the
  repetition series. **You must detect and reject such corrupted repetitions robustly before
  repetition-averaging** — a plain mean over all repetitions is biased by the outlier and
  recovers the wrong perfusion difference (and M0). *Which* subjects and *which* repetitions are
  affected is **not disclosed** — you must find them from the data. Any scientifically valid robust
  scheme is acceptable (outlier rejection on the per-repetition level, robust averaging, etc.).
- **Background-suppression attenuation.** Every readout is background-suppressed by `n_bgs`
  inversion pulses (declared per subject), each attenuating the perfusion difference by the
  per-pulse efficiency `eps`; divide it back out (`dM_true = dM_meas / eps**n_bgs`) before
  quantifying absolute CBF (it cancels in the M0-free rCBF ratio).

Modest Gaussian noise is present on every repetition and does **not** need special handling
beyond the robust average.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `field_T`, `n_vox`, `n_reps`, `tau_s`, `pld_s`, `labeling_efficiency`,
  `T1b_s`, `n_bgs`, `m0_source`, and the file names below. When `m0_source` is `m0_scan` it also
  gives `m0_file`, `m0_tr_s`, `t1_tissue_s`; when it is `sat_recovery` it also gives
  `satrec_file` and `sat_times_s`; when it is `none` no calibration is provided.
- `control.npy`, `label.npy` — float32 arrays of shape `(n_reps, n_vox)`: the background-
  suppressed control and label images, one row per repetition, in the subject's voxel order.
- `m0.npy` — present only for `m0_source = m0_scan`: a proton-density scan of shape
  `(n_m0, n_vox)`.
- `satrec.npy` — present only for `m0_source = sat_recovery`: a saturation-recovery series of
  shape `(n_ti, n_vox)` acquired at the inversion times `sat_times_s`.
- `tissue.npy` — per-voxel tissue label (shape `(n_vox,)`; see the protocol legend, GM = 1,
  WM = 2).
- `mask.npy` — the brain mask (shape `(n_vox,)`).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **determinable** map, each of shape `(n_vox,)` in the subject's
voxel order:
- `rCBF.npy` — relative CBF (dimensionless), the background-suppression-corrected perfusion
  difference divided by its grey-matter median.
- `CBF.npy` — cerebral blood flow in **mL/100g/min** — **only where an M0 source is available**.

Do **not** write a file for a map the subject's acquisition cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for the
maps you can produce so the rest of the cohort can be graded.
