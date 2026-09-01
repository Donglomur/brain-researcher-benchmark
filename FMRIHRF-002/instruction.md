# Voxelwise HRF estimation from a heterogeneous event-related fMRI cohort

## Task
`/app/data/` holds a cohort of single-run event-related fMRI exams (`sub-01` … `sub-08`). Each
subject was scanned while a **target event** was presented repeatedly. From each run, estimate
the per-voxel **evoked haemodynamic response** and write out its shape summaries.

The cohort is **heterogeneous**: every subject's sidecar declares its own repetition time (TR)
and target-onset schedule, and you must adapt the analysis per subject — a pipeline that assumes
one fixed recipe will not fit them all. **Report a shape parameter only where the subject's
design determines it; where it does not, omit that parameter.** There is no reference fitter
provided — implement the estimator yourself and get the units, timing, and per-subject
adaptation right.

Grading is **outcome-based and voxelwise**: each map you write is compared voxel-by-voxel inside
the mask to the *true underlying evoked physiology* — the held-out planted response, summarised
on the noise-free, artifact-free signal. **Any scientifically valid estimator is accepted** (any
FIR construction, solver, drift model, spike detector, or curve-summary reader), because every
correct method recovers the same shape summaries within tolerance. You are **not** required to
reproduce any particular reference implementation's output. Partial cohorts and partial map sets
are scored proportionally, so produce every map you can support and omit the rest.

## Shared model and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the **signal model**
(the percent-BOLD timeseries is a linear convolution of the target onset train with the voxel's
evoked response, plus slow drift and noise), the **FIR estimation** recipe (finite-impulse-
response deconvolution over a **24 s** post-onset window at the subject's TR, with a
low-frequency drift model, high-pass ~1/128 Hz), the **identifiability** rule (the response
*shape* is determinable only for a well-spaced / jittered design, where the target FIR design —
the onset regressors alone — is well conditioned; for a rapid, fixed short-interval design the
overlapping responses make those columns near-collinear and the shape is not identifiable), the
exact definitions and **units** of each reported quantity, and the specified peak-normalised
**canonical HRF**. Read it before you start.

## Robustness / data-quality contract  (READ THIS)
The runs are realistic, not clean:

- **Gross motion-spike frames.** In a **majority of subjects a few individual frames are grossly
  corrupted by a motion transient** — a large global BOLD deflection, some placed near target
  onsets. **You must detect and censor (or otherwise model out) these frames before the fit**, or
  the estimated response — and therefore the amplitude, time-to-peak, and FWHM — is biased,
  especially in the low-amplitude voxels. *Which* frames (and which subjects) are corrupted is
  **not disclosed**; detect them from the data (e.g. a robust DVARS / frame-to-frame outlier
  rule). A **minority of runs have no corrupted frame** and need no censoring.
- **Slow drift.** A low-frequency drift nuisance is present in every run and must be modelled
  (a high-pass / DCT drift basis, ~1/128 Hz) so it does not leak into the response estimate.

These are per-frame / per-run nuisances to be modelled or censored, not whole-subject rejections.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `tr_s` (TR, seconds), `n_frames`, `n_vox`, `target_onsets_s` (the target-event
  onset times in seconds; they fall on TR frames), and the `bold_file` / `mask_file` names.
- `bold.npy` — a float32 array of shape `(n_frames, n_vox)`: the run in **percent BOLD signal
  change** (each voxel's temporal mean already removed), in voxel order.
- `mask.npy` — the voxel mask (shape `(n_vox,)`; maps are graded over these voxels).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **computable** map, each of shape `(n_vox,)` in voxel order:
- `amplitude.npy` — the **peak** of the estimated evoked-response curve (percent BOLD) where the
  shape is identifiable; where it is not, the amplitude (beta) of the canonical-HRF GLM regressor
  (the canonical is peak-normalised, so this beta is the peak percent response). **Always
  reported.**
- `ttp.npy` — **time to peak** (seconds): the time of the maximum of the estimated response
  curve — **only where the design identifies the shape**.
- `fwhm.npy` — **full width at half maximum** (seconds): the width of the main positive lobe of
  the estimated response curve at half of its peak — **only where the design identifies the
  shape**.

`ttp` and `fwhm` are read from the estimated response **curve**, not from basis coefficients. Do
**not** write a file for a shape map the subject's design cannot determine.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for the
maps you can produce so the rest of the cohort can be graded.
