# Super-resolution reconstruction of an ultrasound-localization-microscopy cohort

## Task
`/app/data/` holds a cohort of contrast-enhanced ultrasound-localization-microscopy (ULM)
acquisitions (`sub-01` … `sub-08`). Each is a short stack of beamformed frames in which sparse
contrast **microbubbles** flow through a micro-vascular bed. From these frames, reconstruct the
super-resolved **vessel-density** map and, where the acquisition allows, the **blood-speed**
map, and write them out.

The cohort is **heterogeneous**: every subject's sidecar declares its own acquisition (frame
size, frame rate, pixel size, PSF scale, frame count), and you must adapt per subject — a
pipeline that assumes one fixed recipe will not fit them all. **Produce a map only where the
subject's acquisition determines it; where it does not, omit that map.** There is no
reconstruction toolbox provided — implement the localisation, accumulation, and tracking
yourself and get the geometry, units, and per-subject adaptation right.

Grading is **outcome-based and binwise**: each map you write is recomputed from the frames by a
held-out reference and compared bin-by-bin on a fixed grid. Each (subject × map) panel is scored
independently, so partial cohorts and partial map sets earn proportional credit — produce every
map you can support and omit the rest.

## Shared model and output contract (`/app/data/protocol.json`)
A single JSON with the conventions common to all subjects: the **frame model** (what an in-plane
microbubble looks like), the exact definitions of the **vessel-density** map (accumulated
sub-pixel localisation **count** per grid bin, on the pinned `grid_bin_px` grid) and the
**blood-speed** map (**mean speed in mm/s** of tracked inter-frame steps per bin, using each
subject's own `pixel_size_um` and `frame_rate_hz`), the **omit rule** for velocity where tracking
is not supported, the **unit** of each quantity, and the output grid. Read it before you start.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `n_frames`, `H`, `W`, `pixel_size_um`, `frame_rate_hz`, `psf_sigma_px`,
  `grid_bin_px`, `grid_h`, `grid_w`, and `frames_file`.
- `frames.npy` — the beamformed frame stack, a **float16** array of shape `(n_frames, H, W)`
  (cast to float before processing).

## Required outputs (`/app/output/sub-XX/`)
Write one `float32` `.npy` per **supported** map, each of shape `(grid_h, grid_w)`:
- `density.npy` — the vessel-density map (localisation count per bin). Always required.
- `velocity.npy` — the blood-speed map in **mm/s** — **only where microbubble tracking is
  supported**. Omit (write no file) where the acquisition does not support it.

Do **not** write a `velocity.npy` for a subject whose acquisition cannot support tracking.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write the valid `.npy` files you
can produce so the rest of the cohort can be graded.
