# Frequency-dependent diffusion (OGSE) of a heterogeneous diffusion cohort

## Task
`/app/data/` holds a cohort of oscillating-gradient / pulsed-gradient spin-echo (OGSE/PGSE)
diffusion exams (`sub-01` … `sub-08`). Each subject was scanned with one or more
**diffusion-encoding frequency shells**, each a b-value ramp acquired at a fixed frequency.
From these signals, estimate the per-voxel **frequency-dependent diffusion parameters** and
write them out.

The cohort is **heterogeneous**: every subject's sidecar declares the shells it actually
acquired (waveform, diffusion-encoding frequency, echo time, and the b-values), and you must
adapt the analysis per subject — a pipeline that assumes one fixed recipe will not fit them
all. **Compute a quantity only where the subject's acquisition determines it; where it does
not, omit that map.** There is no reference fitter provided — implement the estimators
yourself and get the physics, units, and per-subject adaptation right.

Grading is **outcome-based and voxelwise**: each map you write is recomputed from the signals
by a held-out reference and compared voxel-by-voxel inside the brain-tissue mask. Partial
cohorts and partial map sets are scored proportionally, so produce every map you can support
and omit the rest.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the **signal model**
(mono-exponential diffusion with a linear frequency dispersion `D(f) = D0 + beta·f`), the exact
definitions of **`D_ref`** (the zero-frequency diffusivity `D0`) and **`beta`** (the dispersion
slope `dD/df`, with `f` in Hz), the **estimator** (ordinary least squares on `ln(S)`, with a
separate non-diffusion-weighted baseline per frequency shell), the **unit** of each quantity,
and the **tissue legend**. Read it before you start.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `n_vox` and a `shells` list; each shell gives `name`, `waveform`, `f_hz`
  (the diffusion-encoding frequency, 0 for PGSE), `te_ms`, `b_ms_um2` (the b-values, in
  ms/µm²), and the `file` holding its signal.
- one `<name>.npy` per shell — a float32 array of shape `(n_b, n_vox)`: the magnitude diffusion
  signal, one row per b-value, in the subject's voxel order.
- `tissue.npy` — per-voxel tissue label (shape `(n_vox,)`; see the protocol legend).
- `mask.npy` — the brain-tissue mask (shape `(n_vox,)`; maps are graded over these voxels).

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **computable** map, each of shape `(n_vox,)` in the subject's
voxel order:
- `D_ref.npy` — the zero-frequency diffusivity `D0` (µm²/ms).
- `beta.npy` — the linear dispersion slope `dD/df` (µm²/ms per Hz) — **only where determinable**.

Do **not** write a file for a map the subject's acquisition cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for
the maps you can produce so the rest of the cohort can be graded.
