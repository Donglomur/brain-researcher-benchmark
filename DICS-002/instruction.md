# DICS source-power imaging of a heterogeneous MEG cohort

## Task
`/app/data/` holds a cohort of MEG frequency-domain exams (`sub-01` … `sub-08`). Each subject
was recorded at rest and reduced to **sensor Fourier coefficients** in a single pinned narrow
band, together with a forward **leadfield** on a fixed source grid. Using a DICS (dynamic
imaging of coherent sources) beamformer, estimate the per-source **orientation-invariant power
image** and write it out.

The cohort is **heterogeneous**: every subject's sidecar declares its own acquisition (channel
and source counts, the numerical rank of the sensor data, whether an empty-room noise recording
is available), and you must adapt the analysis per subject — a pipeline that assumes one fixed
recipe will not fit them all.

Grading is **outcome-based and per-source**: each image you write is recomputed from the
Fourier coefficients and the leadfield by a held-out reference and compared source-by-source
over the whole grid. There is no beamformer library provided — implement the estimator yourself
and get the complex linear algebra, the conventions, and the per-subject adaptation right.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the definitions common to all subjects — read it before you start. It pins,
exactly:

- **CSD.** The cross-spectral density is the mean sensor Fourier outer product over epochs and
  band bins, `C = mean_{e,f} f_{e,f} f_{e,f}^H` — an `(n_channels × n_channels)` complex
  Hermitian positive-semidefinite matrix. The noise CSD `N` is the same mean over the empty-room
  coefficients, with the **same** per-term mean normalisation.
- **Regularised inverse.** `Ci` is the rank-truncated, diagonally-loaded inverse of `C`:
  eigendecompose the Hermitian `C = U diag(σ) Uᴴ` with `σ` descending; keep the top
  `R = data_rank` eigenpairs; set `λ = reg_frac · mean(σ₁..σ_R)`; then
  `Ci = Σ_{k=1..R} u_k u_kᴴ / (σ_k + λ)`. For a full-rank subject `R = n_channels` and this is
  the ordinary loaded inverse. `reg_frac` is given in the protocol.
- **Filter.** The unit-gain vector DICS filter for source `s` with leadfield `L_s`
  (`n_channels × 2`) is `W_s = inv(L_sᴴ Ci L_s) · (L_sᴴ Ci)`, of shape `(2 × n_channels)`.
- **Power.** The orientation-invariant source power is `P(s) = real(trace(W_s C W_sᴴ))` (the
  trace over the two orientations). The graded **relative power** image is
  `Prel(s) = P(s) / median_s P(s)` over all grid sources.
- **NAI.** The Neural Activity Index is `NAI(s) = real(trace(W_s C W_sᴴ)) / real(trace(W_s N W_sᴴ))`
  — the source power divided by the projected noise power through the **same** filter.
  Computable **only** where an empty-room noise recording is provided.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `n_channels`, `n_sources`, `n_epochs`, `n_orientations` (= 2), `band_hz`,
  `data_rank` (the numerical rank of the sensor data), `has_noise`, and the file names below.
- `fourier.npy` — complex array of shape `(n_epochs, n_channels, n_band)`: the sensor Fourier
  coefficients at the band bins, in the sidecar's channel order.
- `leadfield.npy` — real array of shape `(n_sources, n_channels, 2)`: the forward field of two
  orthonormal tangential source orientations per grid point, in the sidecar's channel and source
  order.
- `noise_fourier.npy` — complex `(n_noise_epochs, n_channels, n_band)` empty-room coefficients —
  **present only for some subjects** (see `has_noise`).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **computable** image, each of shape `(n_sources,)` in the sidecar's
source order:
- `Prel.npy` — median-normalised orientation-invariant source power (always).
- `NAI.npy` — Neural Activity Index — **only where an empty-room noise recording is provided**.

Do **not** write `NAI.npy` for a subject with no noise recording.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for
the images you can produce so the rest of the cohort can be graded.
