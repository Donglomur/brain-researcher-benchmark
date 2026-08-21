# Hemoglobin mapping from a heterogeneous optical intrinsic-signal cohort

## Task
`/app/data/` holds a cohort of intraoperative **optical intrinsic-signal imaging** acquisitions
(`sub-01` … `sub-08`) of the exposed cortex. Each subject is a reflectance movie of the same
field of view before and during a functional response. From the reflectance, estimate the
per-pixel **change in hemoglobin concentration** and write the maps out.

The cohort is **heterogeneous**: every subject's sidecar declares how it was acquired (the
illumination and camera, the bands, the differential pathlength), and you must adapt the
inversion per subject — a pipeline that assumes one fixed recipe will not fit them all.
**Compute a map only where the acquisition determines it; where it does not, omit that map.**
There is no reference solver provided — implement the modified Beer-Lambert inversion yourself
and get the optics, units, and per-subject adaptation right.

Grading is **outcome-based and per-pixel**: each map you write is recomputed from the
reflectance by a held-out reference and compared pixel-by-pixel inside the exposed-cortex mask.
Partial cohorts and partial map sets are scored proportionally, so produce every map you can
support and omit the rest.

## Shared optics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects:
- the **modified Beer-Lambert model** — for band `b`, `dOD_b = -log10(Rmean_b^response /
  Rmean_b^baseline)`, linear in the concentration **change**: `dOD = E · [dHbO, dHbR]`, solved
  per pixel by **ordinary least squares**;
- the **extinction × pathlength matrix** `E` and exactly how to build it for each acquisition
  type (discrete multi-wavelength vs. camera-spectral-sensitivity-weighted RGB), the pinned
  oxy/deoxy extinction spectra `eps_hbo`/`eps_hbr` and differential-pathlength shape
  `dpf_shape_cm` on the shared `wavelength_grid_nm`, and the per-subject `dpf_scale`;
- the **determinability** rule (report `dHbO`/`dHbR` only where both are uniquely determined;
  report the total `dHbT` wherever the total is determined);
- the **units** (concentrations in µM; log base 10) and the output spec.

Read it before you start.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `acquisition_type` (`multiwavelength` or `rgb`), `dpf_scale`, `n_pixels`,
  `image_shape`, `n_frames`, `baseline_frames`, `response_frames`, and the acquisition's bands:
  `wavelengths_nm` for a multi-wavelength acquisition, or `channels` (each with a `center_nm`
  and a per-`wavelength_grid_nm` `sensitivity` array) for an RGB acquisition.
- `reflectance.npy` — a float32 array of shape `(n_frames, n_bands, n_pixels)`: the measured
  cortical reflectance (fraction), one row per band, in the subject's pixel order.
- `mask.npy` — the exposed-cortex mask (shape `(n_pixels,)`; maps are graded over these pixels).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **determinable** map, each of shape `(n_pixels,)` in the subject's
pixel order, values in **µM**:
- `HbO.npy` — oxy-hemoglobin concentration change — **only where determinable**.
- `HbR.npy` — deoxy-hemoglobin concentration change — **only where determinable**.
- `HbT.npy` — total-hemoglobin concentration change (`dHbO + dHbR`) — **only where determinable**.

Do **not** write a file for a map the acquisition cannot determine. Where a pixel inside the
mask cannot be reliably inverted, write **NaN** for that pixel rather than a spurious finite
value; NaN pixels are compared as a set against the reference.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for
the maps you can produce so the rest of the cohort can be graded.
