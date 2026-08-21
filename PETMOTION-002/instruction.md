# Inter-frame motion correction and kinetic outcome for a dynamic-PET cohort

## Task
`/app/data/` holds a cohort of dynamic-PET exams (`sub-01` … `sub-08`). Each subject is a 4-D
series of 3-D frames acquired on its own timing schedule, with inter-frame head motion. **Register
the frames to the subject's reference frame, correct the motion, then compute the per-region
kinetic outcome** on the corrected series and write it out.

The cohort is **heterogeneous**: every subject's sidecar declares its tracer class and frame
schedule, and you must adapt the analysis per subject — a pipeline that assumes one fixed recipe
will not fit them all. There is no reference tool provided — implement the registration and the
estimators yourself and get the geometry, units, and per-subject adaptation right.

Grading is **outcome-based and per-region**: the vector you write is recomputed from the frames by
a held-out reference and compared region-by-region. Produce the one output your subject's tracer
class supports and omit the other.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the conventions common to all subjects: the **registration** model (the
integer-voxel translation estimated by normalized-cross-correlation argmax on smoothed frames
against the reference frame, the search radius, and how each frame is corrected), the treatment of
frames that are too short to register, the **analysis window**, the exact **kinetic-outcome
definitions** (Patlak `Ki` for an irreversible tracer, reference-tissue `SUVR` for a reversible
one), the **unit** of each quantity, and the **output fork**. Read it before you start.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `tracer_class` (`irreversible` / `reversible`), `grid`, `n_frames`,
  `n_regions`, `frame_start_s` and `frame_end_s` (per-frame boundaries in seconds),
  `reference_frame_index`, `window_start_min`, the two array file names, and — depending on the
  tracer class — `plasma_cp` (arterial plasma activity at each frame mid-time, irreversible
  tracers) or `reference_region_index` (reversible tracers).
- `frames.npy` — float32 `(n_frames, X, Y, Z)`: the dynamic frame series (with inter-frame
  translation).
- `region.npy` — int `(X, Y, Z)`: the region-label volume in the **reference frame's space**
  (labels `0 … n_regions-1` inside the brain, `-1` outside). The masks are fixed; motion moves the
  frames relative to them.

## Graded quantity (definition + convention anchors)
For each subject: estimate every frame's integer-voxel shift by NCC argmax against
`reference_frame_index` (over the pinned search radius, on smoothed frames), correct each frame by
the exact inverse roll, and form each region's per-frame activity as the region-mask mean of the
corrected frame. Then, over the analysis window (`window_start_min`), compute — per region:
- **irreversible → Patlak `Ki`** (mL/min/mL): `Y = C_region(t)/Cp(t)`, `X = (∫₀ᵗ Cp)/Cp(t)` with
  `Cp = plasma_cp`; `Ki` is the ordinary-least-squares slope of `Y` on `X`. Cumulative integrals
  are trapezoidal over frame mid-times (in **minutes**) with the curve `= 0` at `t = 0`.
- **reversible → reference-tissue `SUVR`** (dimensionless): the equal-weight window mean of each
  region's corrected activity divided by that of the `reference_region_index` region.

## Required outputs (`/app/output/sub-XX/`)
Write, per subject, exactly **one** float32 `.npy` vector of shape `(n_regions,)`, fixed by the
tracer class:
- `ki.npy` — irreversible tracers (Patlak `Ki`).
- `suvr.npy` — reversible tracers (reference-tissue `SUVR`).

Do **not** write the other file — the tracer class does not support it.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid output for the
subjects you can, so the rest of the cohort can be graded.
