# Contrast-enhanced ultrasound (CEUS) microbubble perfusion quantification

## Task
`/app/data/` holds a cohort of contrast-enhanced-ultrasound perfusion exams
(`sub-01` … `sub-08`). Each exam recorded a microbubble **time-intensity curve (TIC)** —
region-of-interest mean acoustic intensity versus time — for several regions. From these
curves, estimate the per-region **perfusion quantities** and write them out.

The cohort is **heterogeneous**: every exam's sidecar declares how it was acquired (the
acquisition type, frame rate, how the samples are stored, and — for a destruction–
replenishment study — the destruction frame), and you must adapt the analysis per exam — a
pipeline that assumes one fixed recipe will not fit them all. **Report a quantity only where
the acquisition determines it; where it does not, omit it.** There is no reference fitter
provided — implement the estimators yourself and get the model, units, and per-exam adaptation
right.

Grading is **outcome-based**: each quantity you report is recomputed from the TICs by a
held-out reference and compared per region per quantity. Partial cohorts and partial quantity
sets are scored proportionally, so produce every quantity you can support and omit the rest.

## Shared conventions and output contract (`/app/data/protocol.json`)
A single JSON with the conventions common to all exams: the **data-scale convention** (how to
map stored samples to linear acoustic intensity), the **time convention** (`t = frame / fps`),
the **bolus** and **destruction–replenishment** TIC **models**, the exact **definition of each
reported quantity**, the **unit** of each, and the **output spec**. Read it before you start.

The graded quantities are pinned as follows (all in the exam's linear intensity units, with
enhancement measured above the fitted baseline `offset`):

- **bolus** exams — fit the log-normal TIC and report, per region:
  `PE` (peak enhancement, `max_t E(t)`), `WiR` (wash-in rate, `max_t dE/dt` of the fitted
  curve), `TTP` (time-to-peak from `t=0`, `= t0 + exp(mu − sigma^2)`, seconds), and
  `AUC` (integral of `E(t)` over the acquisition window `[0, T]`).
- **replenishment** exams — fit the post-flash mono-exponential
  `I(tau) = offset + A·(1 − exp(−beta·tau))` and report, per region: `beta` (replenishment
  rate, 1/s), `A` (plateau enhancement), and `PI` (perfusion index `= A·beta`).

## Per exam (`/app/data/sub-XX/`)
- `sidecar.json` — `acquisition_type` (`"bolus"` or `"replenishment"`), `fps`, `n_frames`,
  `data_scale` (`"linear"` or `"log_db"`), the `regions` list (names), the `tic_file`, and —
  for a replenishment exam — `flash_frame` (the frame at which the steady-state bubbles are
  destroyed).
- `<tic_file>.npy` — a float32 array of shape `(n_regions, n_frames)`: the region-mean TIC
  samples in the exam's stored units, one row per region in the sidecar's region order.

## Required output (`/app/output/sub-XX.json`)
For each exam write one JSON object mapping each region name to an object of its **determinable**
quantities, e.g. for a bolus exam
`{"core": {"PE": .., "WiR": .., "TTP": .., "AUC": ..}, "rim": {...}, ...}`
and for a replenishment exam
`{"core": {"beta": .., "A": .., "PI": ..}, ...}`.
Include a quantity key **only** where the acquisition supports it; omit the key (or set it
`null`) otherwise.

## Failure handling
If a region cannot be processed for an unexpected reason, still write valid entries for the
regions and quantities you can produce so the rest of the cohort can be graded.
