# dSPM source reconstruction of a heterogeneous EEG cohort

## Task
`/app/data/` holds a cohort of EEG evoked-response exams (`sub-01` … `sub-08`). Each subject
provides a fixed-orientation leadfield and an evoked sensor topography, together with a sensor
**noise model**. From these, estimate the **dSPM (noise-normalised minimum-norm) source
distribution** and write out, for every source, its noise-normalised **power** over the epoch.

The cohort is **heterogeneous**: each subject's sidecar declares its acquisition (the electrode
reference scheme, the signal-to-noise ratio, and whether a noise covariance or only a
pre-stimulus baseline is provided), and you must adapt the inverse operator per subject — a
pipeline that assumes one fixed recipe will not fit them all.

Grading is **outcome-based and sourcewise**: the power map you write is recomputed from the
leadfield, evoked data, and noise model by a held-out reference and compared source-by-source
over the well-constrained source grid. Get the physics, the whitening, and the per-subject
adaptation right — no inverse solver is provided; implement it yourself.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the definitions common to all subjects: the **signal model** `b(t) = G j(t)
+ noise`; the **minimum-norm inverse** with identity source covariance (`R = I`, no depth
weighting); the **whitening** of the sensor data by the noise covariance `C` (using the
reduced-rank pseudo-whitener when `C` is rank-deficient); the **regularisation**
`lambda^2 = trace(Gtil Gtil^T) / (r * SNR^2)` with `r = rank(C)`; the **dSPM noise
normalisation** `noise_norm_k = sqrt((Mtil Mtil^T)_kk)`; the **graded quantity**
`P_k = mean_t dSPM_k(t)^2`; and the rule for **estimating** `C` from a baseline when none is
shipped. Read it before you start.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `n_chan`, `n_src`, `n_time`, `reference` (`"average"` or `"mastoid"`),
  `snr`, and the file names below. When a noise covariance is not shipped, `baseline_file`
  names a pre-stimulus baseline and `n_baseline` its sample count.
- `leadfield.npy` — the fixed-orientation leadfield `G`, shape `(n_chan, n_src)`. Use it as
  given (identity source covariance).
- `evoked.npy` — the sensor data to localise, shape `(n_chan, n_time)`.
- `noise_cov.npy` — the sensor noise covariance `C`, shape `(n_chan, n_chan)` — **when shipped**.
- `baseline.npy` — a pre-stimulus baseline, shape `(n_chan, n_baseline)` — **when the
  covariance is not shipped**; estimate `C` from it as defined in the protocol.

## Required output (`/app/output/sub-XX/`)
Write one float32 `.npy` per subject:
- `dspm_power.npy` — the noise-normalised dSPM source power `P_k`, shape `(n_src,)`, in the
  leadfield's source order.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write a valid `dspm_power.npy`
for the subjects you can produce so the rest of the cohort can be graded.
