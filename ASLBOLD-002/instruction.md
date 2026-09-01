# Dual-echo simultaneous ASL+BOLD: perfusion, BOLD and calibrated CMRO2

## Task
`/app/data/` holds a cohort of dual-echo pseudo-continuous ASL (pCASL) exams (`sub-01` … `sub-08`).
Each subject was scanned during a functional **task** with an acquisition that **interleaves
control and label images** and reads each image out at **two (or three) echo times** — so a single
run carries both the **perfusion** signal (the control−label difference) and the **BOLD** signal
(the later, T2\*-weighted echo). Some subjects additionally had a **hypercapnia** calibration run.
From these signals, estimate the per-voxel **quantitative maps** and write them out.

The cohort is **heterogeneous**: every subject's sidecar declares the runs, echo times, timing and
references it actually acquired, and you must adapt the analysis per subject — a pipeline that
assumes one fixed recipe will not fit them all. **Compute a map only where the subject's acquisition
determines it; where it does not, omit that map.** There is no reference pipeline provided —
implement the estimators yourself and get the physics, units, and per-subject adaptation right.

Grading is **outcome-based and voxelwise against the true underlying physiology**. Each map you
write is compared voxel-by-voxel, inside the grey-matter mask, to the *true* quantity that
generated the signals (the baseline CBF and the **drift-free** task responses). **Any
scientifically valid estimator is accepted** — any surround/detrend perfusion scheme, any
linear-drift BOLD nuisance regressor, a GLM or a block percent-change — because every correct
method recovers the same physiology within tolerance. You are **not** required to reproduce any
particular reference implementation's output. Each (subject × map) is scored independently, so
produce every map you can support and omit the rest.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the dual-echo **signal
model**; how the **perfusion** (control−label) difference and the **absolute CBF** (Alsop 2015
single-compartment pCASL, mL/100g/min) are formed, including the **M0 reference** rule (a dedicated
M0 scan when provided, otherwise the saturation-corrected control image); the **BOLD** signal
definition and the **percent-change** convention; the **Davis (1998)** model, the hypercapnia
**M-value**, and the relative-**CMRO2** inversion; the fixed model constants (`lambda`,
`alpha_label`, the field-dependent `T1_blood`/`T1_tissue`, `alpha`, the field-dependent `beta`); the
**unit** of each quantity; and the **tissue legend**. Read it before you start.

## Robustness / data-quality contract  (READ THIS)
The signals are realistic, not clean:

- **M0 reference depends on the acquisition.** Subjects acquired with **background suppression**
  carry a dedicated **M0 scan** (`m0.npy`); their control image is *not* a valid
  equilibrium-magnetization reference (its static tissue is strongly suppressed), so you **must**
  use the M0 scan. Subjects **without** a dedicated M0 scan derive M0 from the control image with
  a saturation-recovery correction. Reading CBF off the wrong M0 over/under-scales it by a large
  factor. `background_suppression` and the presence of `m0_file` tell you which case a subject is.
- **Low-frequency common-mode drift.** A slow signal drift (approximately linear across the run)
  rides on the static-tissue magnetization on a **subset of subjects** (it is a scanner/system
  effect and appears **regardless of background suppression**). It biases **both** graded pathways
  unless removed **consistently**:
  - **Perfusion** — because control and label images are acquired half a TR apart, the drifting
    static tissue (≈100× larger than the perfusion difference) leaks into a **simple pairwise**
    control−label subtraction (≈100× amplified) as a spurious perfusion change. Use a **surround**
    subtraction (control minus the average of the two temporally adjacent label frames) or an
    equivalent detrended difference, which removes a linear trend exactly.
  - **BOLD** — the control BOLD timeseries carries the drift directly, so a plain block-mean
    active-vs-baseline contrast reads the drift as a spurious BOLD change. **Remove a linear-in-time
    drift nuisance** (a drift regressor fitted jointly with the activation block, or any equivalent
    detrend) before the contrast.

  *Which* subjects drift is **not disclosed** — you must handle it robustly everywhere. Removing
  the drift from only one pathway leaves the calibrated CMRO2 biased. Any scientifically valid
  detrend is accepted.

Modest Rician noise is present on every frame and does **not** need special handling beyond an
ordinary fit.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `field_T`, `n_vox`, the echo times `te_ms`, the sequence `tr_s`, the
  `label_duration_s` and `post_label_delay_s`, `background_suppression`, an `m0_file` (only when a
  dedicated M0 scan was acquired), and a `runs` list. Each run gives `name`, `condition` (`task` or
  `hypercapnia`), the `file`, `n_frames`, the `frame_types` (per-frame `control`/`label` labels),
  and the `baseline_pairs` / `active_pairs` (indices into the control-label pair sequence).
- one `<run>.npy` per run — a float32 array of shape `(n_frames, n_echoes, n_vox)`: the magnitude
  images in the subject's voxel order, with control and label frames interleaved per `frame_types`
  and one slice per echo time.
- `m0.npy` — present only when `m0_file` is set: the dedicated M0 reference, shape
  `(n_echoes, n_vox)`.
- `tissue.npy` — per-voxel tissue label (shape `(n_vox,)`; see the protocol legend, grey matter = 1).
- `gm_mask.npy` — the grey-matter mask (shape `(n_vox,)`; maps are graded over these voxels).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **computable** map, each of shape `(n_vox,)` in the subject's voxel
order, in the units defined by the protocol:
- `CBF.npy` — baseline absolute perfusion (mL/100g/min).
- `rBOLD.npy` — relative BOLD change during the task (%).
- `rCBF.npy` — relative CBF change during the task (%).
- `rCMRO2.npy` — relative CMRO2 change during the task (%) — **only where a hypercapnia calibration
  determines it**.

Do **not** write a file for a map the subject's acquisition cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for the
maps you can produce so the rest of the cohort can be graded.
