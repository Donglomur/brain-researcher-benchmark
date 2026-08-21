# Total quantitative susceptibility mapping (QSM) of a heterogeneous cohort

## Task
`/app/data/` holds a cohort of quantitative-susceptibility exams (`sub-01` … `sub-08`). Each
subject provides a background-removed **local tissue-phase** echo train and a brain mask; some
also provide a CSF reference ROI. From the phase, estimate the per-voxel **local field** and the
per-voxel **total magnetic susceptibility**, and write them out.

The cohort is **heterogeneous**: every subject's sidecar declares exactly what it has (echo
times, field strength, whether a CSF reference ROI is present), and you must adapt the analysis
per subject — a pipeline that assumes one fixed recipe will not fit them all. **Report a
susceptibility map only in the reference frame the subject's acquisition determines; produce the
other frame's file for no subject.**

Grading is **outcome-based and voxelwise**: each map you write is recomputed from the phase by a
held-out reference and compared voxel-by-voxel inside the brain mask. Partial cohorts are scored
proportionally, so produce every map you can for every subject.

## Shared physics and output contract (`/app/data/protocol.json`)
A single JSON with the physics and conventions common to all subjects: the **grid / B0
convention** (how each flattened `(n_vox,)` array maps to a 3D volume, and which axis is B0), the
multi-echo **field model** (local phase `φ(TE) = φ0 + 2π·df·TE`; the normalised field
`delta = df / f0_mhz`, in ppm), the **pinned closed-form Tikhonov dipole inversion** (the exact
k-space operator, kernel, and `lambda` that turn the field into susceptibility), and the
**referencing rule** (which reference region defines the zero of susceptibility, and how the
offset is computed). Read it before you start — the inversion and referencing are fixed
conventions, and reproducing them is the point.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `field_T`, `f0_mhz`, `grid` (the 3D shape), `n_vox`, `te_ms` (the echo
  times), and the `phase_file` / `mask_file` names; `csf_ref_file` is present **only for some
  subjects**.
- `phase.npy` — float32 `(n_echoes, n_vox)`: the local tissue phase (radians), one row per echo,
  in the subject's voxel order (0 outside the brain).
- `mask.npy` — the brain mask (`(n_vox,)`; maps are graded over these voxels).
- `csf_ref.npy` — a CSF reference ROI (`(n_vox,)`), **present only for some subjects**.

## Required outputs (`/app/output/sub-XX/`)
Write float32 `.npy` maps of shape `(n_vox,)` in the subject's voxel order:
- `field.npy` — the normalised local field `delta` (ppm) — for **every** subject.
- `chi_abs.npy` — CSF-referenced (absolute) total susceptibility (ppm) — **only** for a subject
  that has a CSF reference ROI.
- `chi_rel.npy` — whole-brain-referenced (relative) total susceptibility (ppm) — **only** for a
  subject that has no CSF reference ROI.

Write exactly one of `chi_abs` / `chi_rel` per subject (whichever the referencing rule supports),
plus `field`. Do **not** write the susceptibility file the subject does not support.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write valid `.npy` files for the
maps you can produce so the rest of the cohort can be graded.
