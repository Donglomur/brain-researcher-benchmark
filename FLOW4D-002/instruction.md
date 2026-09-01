# Phase-contrast / 4D-flow velocity quantification of a heterogeneous cohort

## Task
`/app/data/` holds a cohort of phase-contrast (velocity-encoded) MRI exams
(`sub-01` … `sub-08`). Each subject is a single 2D analysis slice through a vessel, acquired
with one or more velocity-encoded directions. From the magnitude and phase images, quantify the
flow and write the results out.

The cohort is **heterogeneous**: every subject's sidecar declares the velocity directions it
actually encoded (each with its own encoding vector and VENC), the slice normal, and the pixel
area — and you must adapt the analysis per subject. **Compute a quantity only where the
subject's acquisition determines it; where it does not, omit it.** There is no reference tool
provided — implement the velocity reconstruction yourself and get the physics, units, and
per-subject adaptation right.

Grading is **outcome-based and physical**: each quantity you write is compared to the *true
underlying flow* that generated the images — the held-out planted velocity field, quantified on
the noise-free, artifact-free signal. **Any scientifically valid estimator is accepted** (any
lumen threshold, any background-fit order, any aliasing-unwrap scheme, any noise masking),
because every correct method recovers the same convention-invariant velocity magnitudes within
tolerance. You are **not** required to reproduce any particular reference implementation's
output. Partial cohorts and partial quantity sets are scored proportionally, so produce every
quantity you can support and omit the rest.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the conventions common to all subjects: the **velocity convention**
(`v = VENC × phase / π`, with the phase-difference image wrapped into `(-π, π]` and signed
along the encoding direction), the definition of the per-voxel flow **speed** (the magnitude of
the encoded velocity vector), the **peak velocity** (the 99th-percentile flow speed over the
lumen), the **net flow** (`Q = Σ_lumen (v · n̂) · pixel_area`, in mL/s, reported as a magnitude,
and determinable only where the acquisition encodes a component along the slice normal `n̂`),
the **lumen** definition, the **units**, and the exact **output spec**. Read it before you
start.

## Robustness / data-quality contract  (READ THIS)
The images are realistic, not clean:

- **Eddy-current / background-phase drift.** A **majority of subjects** carry a smooth
  background-phase offset (a planar eddy-current drift over the whole field of view) that puts a
  spurious velocity on static tissue. **You must fit it over static tissue — excluding the
  vessel lumen and the low-signal air — and remove it** (in phase space) before quantifying
  velocity, or the peak and net flow are biased. *Which* subjects carry it is **not disclosed**;
  a minority have none. Any scientifically valid background-fit (planar, quadratic, …) is
  accepted.
- **Single-band phase aliasing.** In a **majority of subjects the peak velocity exceeds the
  VENC**, so the phase-difference image **aliases**: the vessel core wraps into a
  physically-impossible reverse-flow value, and you **must detect and unwrap it** (single-band:
  the wrapped forward-flow core gets `+2·VENC`) before the velocity is trustworthy. Subjects
  within VENC must **not** be unwrapped. *Which* subjects alias is **not disclosed** — find it
  from the data.
- **Air noise.** The field of view outside the tissue is pure noise (random phase); its low
  magnitude must mask it out of both the lumen segmentation and the background fit, or it
  corrupts both.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `grid_shape` (`[ny, nx]`, row-major), `slice_normal` (a 3-vector `n̂`),
  `pixel_area_cm2`, the `magnitude_file`, the `roi_file`, and an `encodings` list; each encoding
  gives `name`, `direction` (a 3-vector unit encoding direction), `venc_cms`, and the `phase_file`
  holding its phase-difference image.
- `magnitude.npy` — the magnitude image, float32, shape `(n_vox,)` in `(ny, nx)` row-major order.
- one `phase_<name>.npy` per encoded direction — the wrapped phase-difference image (radians),
  float32, shape `(n_vox,)`, same voxel order.
- `roi.npy` — the analysis region (`(n_vox,)`); the vessel lumen is the high-signal region within it.

## Required outputs (`/app/output/sub-XX/`)
Write, in the subject's voxel order:
- `speed.npy` — float32, shape `(n_vox,)` — the per-voxel flow speed (cm/s). Graded over the lumen.
- `peak_velocity.npy` — float32, shape `(1,)` — the peak velocity (cm/s).
- `net_flow.npy` — float32, shape `(1,)` — the net volumetric flow (mL/s) — **only where determinable**.

Do **not** write `net_flow.npy` for a subject whose acquisition cannot determine it.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid files for the
quantities you can produce so the rest of the cohort can be graded.
