# Phase-amplitude cross-frequency coupling in a heterogeneous recording cohort

## Task
`/app/data/` holds a cohort of single-channel neural recordings (`sub-01` … `sub-08`). Each was
delivered as a set of independent epochs. From each recording, estimate the **phase-amplitude
cross-frequency coupling** — the Tort modulation index between a low-frequency phase band and a
high-frequency amplitude band — and write out the results.

The cohort is **heterogeneous**: every recording's sidecar declares its sampling rate, epoch
geometry, and the exact bands to use, and you must adapt the analysis per recording — a pipeline
that assumes one fixed recipe will not fit them all. **Compute a quantity only where the
recording supports it; where it does not, omit it.** There is no PAC library provided — implement
the estimators yourself and get the conventions, units, and per-recording adaptation right.

Grading is **outcome-based**: each quantity you write is recomputed from the signals by a
held-out reference and compared. Partial cohorts and partial quantity sets are scored per panel,
so produce every quantity you can support and omit the rest.

## Shared conventions and output contract (`/app/data/protocol.json`)
A single JSON with the analysis conventions common to all recordings — read it before you start.
It pins, exactly:

- the **band-pass**: a zero-phase FIR (Hamming-windowed sinc, length = 3 cycles of the pass-band's
  low edge rounded up to an odd number of taps), applied forward-and-backward, i.e.
  `scipy.signal.firwin(ntaps, [lo, hi], pass_zero=False, fs=fs, window="hamming")` then
  `scipy.signal.filtfilt`. **Phase** is the angle of the analytic (Hilbert) signal of the
  phase-band trace; **amplitude** is the magnitude of the analytic signal of the amplitude-band
  trace.
- the **modulation index** `MI`: the Tort (2010) Kullback-Leibler index with **exactly 18** equal
  phase bins over `[-π, π)` — bin the phase, take the mean amplitude per bin, normalise the 18
  means to a distribution `p`, and `MI = (ln 18 − H(p)) / ln 18` with `H(p) = −Σ pₖ ln pₖ`. Use the
  **raw** index — no surrogate normalisation, z-scoring, or bias subtraction.
- the **preferred phase**: the **circular mean** of the mean-amplitude-versus-phase distribution,
  `angle(Σ pₖ e^{i θₖ})`, with `θₖ` the 18 bin centres.
- the **comodulogram**: `MI` (same pinned pipeline) over the grid of
  `comod_phase_bands × comod_amp_bands` named in the sidecar.

Pool the per-epoch phase and amplitude series across a recording's epochs before binning.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `fs_hz`, `n_epochs`, `n_samples`, `epoch_len_s`, the pinned `phase_band` and
  `amp_band` (Hz), and the comodulogram grid `comod_phase_bands` / `comod_amp_bands`.
- `signal.npy` — the recording, a float32 array of shape `(n_epochs, n_samples)`: one row per
  epoch, in acquisition order.

## Required outputs (`/app/output/sub-XX/`)
Write float32 `.npy` files:
- `mi.npy` — the single-band Tort modulation index (a scalar) at the sidecar's
  `phase_band × amp_band`. **Always.**
- `preferred_phase.npy` — the preferred coupling phase (a scalar, radians) — **only when the
  channel couples**, i.e. `MI ≥ 0.004`; otherwise omit it.
- `comodulogram.npy` — the 2-D MI grid, shape `(len(comod_phase_bands), len(comod_amp_bands))` —
  **only when the recording's nominal duration** (`n_epochs × epoch_len_s`) **is at least 90 s**;
  otherwise omit it.

Do **not** write a file for a quantity the recording does not support.

## Failure handling
If a recording cannot be processed for an unexpected reason, still write valid `.npy` files for
the quantities you can produce so the rest of the cohort can be graded.
