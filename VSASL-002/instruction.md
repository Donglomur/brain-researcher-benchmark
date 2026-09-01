# Velocity-selective ASL (VS-ASL) cerebral blood flow quantification

## Task
`/app/data/` holds a cohort of velocity-selective arterial-spin-labeling (VS-ASL) perfusion
exams (`sub-01` … `sub-08`). Each subject was scanned with many label/control repetitions of a
single-delay velocity-selective ASL acquisition. From these signals, estimate the per-voxel
**cerebral blood flow (CBF)** in **mL/100g/min** and write it out.

The cohort is **heterogeneous**: each subject's sidecar declares how it was labeled and
calibrated (the labeling module, the inversion time, the cutoff velocity, and how to obtain the
equilibrium magnetization M0), and you must adapt the quantification per subject — a pipeline
that assumes one fixed recipe will not fit them all. **Compute CBF only where the subject's
calibration determines it; where it does not, omit the map.** There is no reference quantifier
provided — implement the estimator yourself and get the physics, units, and per-subject
adaptation right.

Grading is **outcome-based and voxelwise against the true underlying physiology**: the CBF map you
write is compared voxel-by-voxel, inside the grey- and white-matter masks, to the *true* CBF that
generated the signals. **Any scientifically valid estimator is accepted** — any robust repetition
average, any M0 arithmetic, any linear algebra — because every correct method recovers the same
physiology within tolerance; you are **not** required to reproduce any particular reference
implementation's output. Subjects (and each subject's GM / WM regions) are scored independently,
so produce every map you can support and omit the rest.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the transit-time-insensitive
single-compartment **signal model** relating the repetition-averaged perfusion difference
`dM = <control> − <label>` to CBF, the **labeling modules** (velocity-selective saturation vs
inversion) and their constants, the **M0 calibration** paths, the shared physical constants
(blood T1, partition coefficient, labeling efficiencies), the **unit** of CBF, and the **tissue
legend**. Read it before you start.

## Robustness / data-quality contract  (READ THIS)
The signals are realistic, not clean:

- **Grossly corrupted repetitions.** In a **majority of subjects, one or two individual
  label/control repetitions are grossly corrupted** (a whole image scaled by a large motion /
  inversion-failure factor) and are physically inconsistent with the other repetitions. **You
  must detect and reject such corrupted repetitions robustly before averaging** the perfusion
  difference `dM = <control> − <label>` (and any control-derived M0). *Which* subjects and *which*
  repetitions are affected is **not disclosed** — you must find them from the data. Any
  scientifically valid robust scheme is acceptable (outlier rejection on a per-repetition summary
  statistic, a per-voxel median, robust averaging, …); a plain mean over all repetitions recovers
  the wrong `dM`/M0 on the affected subjects and fails those panels. The corruptions are gross
  (far larger than the per-repetition noise scatter), so a wide robust margin rejects them without
  dropping any legitimate repetition.
- **Module and calibration forks.** The labeling module (VSS vs VSI) sets **both** κ and α, and
  the M0-calibration path depends on what the subject provides (a fully-relaxed M0 scan, a
  saturation-recovery-corrected proton-density control, or none → omit). Applying the wrong module
  math or the wrong M0 path biases CBF. See the protocol.

Modest additive noise is present on every repetition and does **not** need special handling beyond
the ordinary robust average.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `field_T`, `n_vox`, `label_module`, `cutoff_velocity_cm_s`, `TI_s`, `n_reps`,
  `m0_source`, and the file names below. When `m0_source` is `control_pd` it also gives
  `tr_ctrl_s` and `t1_tissue_s`; when it is `m0_scan` it also gives `m0_file`.
- `control.npy`, `label.npy` — float32 arrays of shape `(n_reps, n_vox)`: the control and label
  images, one row per repetition, in the subject's voxel order.
- `m0.npy` — present only for `m0_source = m0_scan`: a fully-relaxed reference of shape
  `(n_m0, n_vox)`.
- `tissue.npy` — per-voxel tissue label (shape `(n_vox,)`; see the protocol legend, GM = 1,
  WM = 2).
- `mask.npy` — the brain mask (shape `(n_vox,)`).

## Required output (`/app/output/sub-XX/`)
- `CBF.npy` — a float32 array of shape `(n_vox,)` in the subject's voxel order, CBF in
  **mL/100g/min** — **only where determinable**.

Do **not** write `CBF.npy` for a subject whose calibration cannot yield absolute CBF.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid outputs for the
subjects you can process so the rest of the cohort can be graded.
