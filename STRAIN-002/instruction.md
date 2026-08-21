# Cardiac-induced brain micro-displacement and strain from gated phase MRI

## Task
`/app/data/` holds a cohort of gated brain-motion exams (`sub-01` … `sub-09`). Each subject was
scanned with a phase-based sequence that encodes the sub-voxel tissue motion driven by the
cardiac cycle. From the phase data, estimate the per-voxel **displacement magnitude** and, where
the acquisition determines it, the **principal strain**, and write them out.

The cohort is **heterogeneous**: every subject's sidecar declares its acquisition — whether the
phase encodes displacement directly (DENSE) or velocity (phase-contrast), and whether a diastolic
reference/baseline was acquired — and you must adapt the analysis per subject; a pipeline that
assumes one fixed recipe will not fit them all. **Compute a map only where the subject's
acquisition determines it; where it does not, omit that map.** There is no reference tool
provided — implement the estimators yourself and get the physics, units, and per-subject
adaptation right.

Grading is **outcome-based and voxelwise**: each map you write is recomputed from the phase data
by a held-out reference and compared voxel-by-voxel. Partial cohorts and partial map sets are
scored proportionally, so produce every map you can support and omit the rest.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the **displacement
definition** for each acquisition type (DENSE: `d_i = wrap(mean(enc_i) − mean(ref_i)) / ke_i`
in micrometres; phase-contrast: `v_i = VENC_i · wrap(phase_i) / π` integrated over the cardiac
cycle, taking the frame of maximum mean displacement), the **background-correction convention**
(a planar detrend of the displacement field over the static-tissue voxels), the exact
**strain definition** (`pstrain` = the largest eigenvalue of the symmetric displacement-gradient
tensor `E = (G + Gᵀ)/2`, with `G` formed by `numpy.gradient` second-order central differences at
the given voxel spacing), the **reference rule** (strain is determinable only where a diastolic
reference/baseline is present), the **unit** of each quantity, and the tissue legend. Read it
before you start.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `acquisition` (`dense`/`pc`), `reference_phase` (bool), `grid_shape`,
  `voxel_mm`, `n_vox`, the per-direction encoding (`ke_rad_per_um` for DENSE, `venc_um_per_s`,
  `frame_times_s`, `baseline_frame` for PC), and the list of phase files per direction.
- the per-direction phase `.npy` files named in the sidecar — float32 radians, wrapped to
  `(-π, π]`, in the subject's voxel order:
  - DENSE: `enc_{x,y,z}.npy` of shape `(n_avg, n_vox)`, and — when a reference was acquired —
    `ref_{x,y,z}.npy`.
  - PC: `vel_{x,y,z}.npy` of shape `(n_frames, n_vox)`, one row per cardiac frame.
- `static.npy` — boolean `(n_vox,)`, the extra-brain static-tissue voxels (true displacement
  zero) used for the background correction.
- `tissue.npy` — per-voxel tissue label `(n_vox,)` (see the protocol legend).
- `mask.npy` — the brain mask `(n_vox,)`; `disp_um` is graded over these voxels.

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `.npy` per **determinable** map, each of shape `(n_vox,)` in the subject's
voxel order:
- `disp_um.npy` — displacement magnitude (micrometres).
- `pstrain.npy` — maximum principal strain (dimensionless) — **only where determinable**
  (`reference_phase = true`); `pstrain` is graded over the interior brain voxels.

Do **not** write a file for a map the subject's acquisition cannot support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for the
maps you can produce so the rest of the cohort can be graded.
