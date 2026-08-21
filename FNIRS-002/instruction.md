# Haemoglobin concentration changes from a heterogeneous continuous-wave fNIRS cohort

## Task
`/app/data/` holds a cohort of continuous-wave near-infrared spectroscopy (fNIRS) runs
(`sub-01` … `sub-08`). Each subject was recorded on a multi-channel device that sampled the
tissue at two or three near-infrared wavelengths. From the raw light-intensity time series,
estimate the per-channel **haemoglobin (and, where the device supports it, cytochrome)
concentration-change traces** and write them out.

The cohort is **heterogeneous**: every subject's sidecar declares the wavelengths the device
actually acquired, the per-wavelength differential pathlength factor, and the per-channel
source–detector distance, and you must adapt the analysis per subject — a device that samples
only two wavelengths cannot resolve the third chromophore, so **produce a chromophore only where
the acquisition determines it and omit it otherwise.** There is no fitter provided — implement
the modified Beer–Lambert inversion yourself and get the physics, units, and per-subject
adaptation right.

Grading is **outcome-based and per channel**: each concentration trace you write is recomputed
from the raw intensity by a held-out reference and compared frame-by-frame. Partial cohorts and
partial channel/chromophore sets are scored proportionally, so produce every trace you can
support and omit the rest.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects:

- **Optical density.** The baseline intensity `I0(λ)` for a channel/wavelength is the **mean**
  of the raw intensity over the baseline-window frames `[0, baseline_frames)`. The change in
  optical density is `dOD(λ, t) = log10( I0(λ) / I(λ, t) )` (**base-10**, attenuation-positive).
- **Modified Beer–Lambert law.** `dOD(λ, t) = Σ_k eps(λ, k) · dC_k(t) · L(λ)` over chromophores
  `k`, with effective optical pathlength `L(λ) = SD_distance · DPF(λ)`. Assemble the device
  wavelengths into `E[i, k] = eps(λ_i, k) · SD_distance · DPF(λ_i)` and solve `E · dC = dOD` at
  every frame. The **base-10 molar extinction coefficients** `eps(λ, k)` (L·mol⁻¹·cm⁻¹) are
  tabulated in the protocol; use the sidecar `dpf` and `sd_distance_cm`. With two wavelengths the
  chromophores are `(HbO, HbR)`; with three they are `(HbO, HbR, CCO)` and the 3×3 system is
  exactly determined.
- **Units.** Report concentration changes in **micromolar (µM = µmol/L)**.

Read it before you start.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `n_channel`, `n_wavelength`, `n_frame`, `wavelengths_nm`, `dpf` (per
  wavelength), `sd_distance_cm` (per channel), `baseline_frames`, `sampling_rate_hz`, and the
  `intensity_file`.
- `intensity.npy` — a float32 array of shape `(n_channel, n_wavelength, n_frame)`: the raw
  continuous-wave light intensity, in the sidecar's channel and wavelength order.

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **supported** chromophore, each of shape `(n_channel, n_frame)` in
the subject's channel and frame order, in **micromolar**:
- `HbO.npy` — oxy-haemoglobin concentration change.
- `HbR.npy` — deoxy-haemoglobin concentration change.
- `CCO.npy` — oxidised-minus-reduced cytochrome-c-oxidase change — **only for a device that
  resolves it** (three wavelengths). Do **not** write `CCO.npy` for a two-wavelength device.

Where a particular `(channel, frame)` does not support a reliable concentration estimate, store
`NaN` for that entry rather than a fabricated value.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for the
channels you can produce so the rest of the cohort can be graded.
